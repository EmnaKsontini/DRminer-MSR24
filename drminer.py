#!/usr/bin/env python
from Dockerfile_EAST import get_EAST
from Matching import match_trees,preprocess,extract_stages,extract_instructions, match_components_round1, match_components_round2
import os
import copy
import git
import os
import json
import shutil
import pandas as pd
from tqdm import tqdm
import argparse
def set_rw_and_execute(path, mode):
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chmod(os.path.join(root, d), mode)
        for f in files:
            os.chmod(os.path.join(root, f), mode)

def detect_extract_run_instructions(UI_1, UI_2, MS):
    refactorings = []
    for s1, s2 in MS:
        for i2 in UI_2:
            if i2 in s2 and i2['name'] == 'RUN' and any(child['name'] == 'script' for child in i2['children']):
                scripts_i2 = [child['children'][0]['name'] for child in i2['children'] if child['name'] == 'script']
                matched_instructions = []
                remove_instructions = []
                for i1 in UI_1:
                    if i1 in s1 and i1['name'] == 'RUN':

                        commands_i1 = [child['children'][0]['name'] for child in i1['children'] if child['name'] == 'command']

                        for script in scripts_i2:
                            for cmd in commands_i1:
                                if cmd in str(script):

                                    matched_instructions.append(i1)
                                    remove_instructions.append(i1)
                                    break

                for i in remove_instructions:  
                    UI_1.remove(i)
                

                if matched_instructions:
                    refactorings.append((i2, matched_instructions))  
                    UI_2.remove(i2)

    return refactorings
def detect_added_instructions(UI_2, instruction_name, child_name):

    added_instructions = [instruction for instruction in UI_2 if instruction['name'] == instruction_name]
    
    refactoring_values = []
    for ins in added_instructions:
        child_node = [child for child in ins['children'] if child['name'] == child_name]
        if child_node and child_node[0]['children']:
            refactoring_values.append(child_node[0]['children'][0]['name'])

    UI_2[:] = [instruction for instruction in UI_2 if instruction['name'] != instruction_name]

    return refactoring_values
def detect_replace_add_with_copy(MI, MS):
    refactorings = []
    for s1, s2 in MS:
        for i1 in s1:
            if i1['name'] == 'ADD':
          
                for i2 in s2:
                    if (i1, i2) in MI and i2['name'] == 'COPY':
                        refactorings.append((i1, i2))
                        
    return refactorings
def are_instructions_equal(instr1, instr2):
    return instr1['name'] == instr2['name'] and all(
        are_instructions_equal(child1, child2)
        for child1, child2 in zip(instr1.get('children', []), instr2.get('children', []))
    )
def get_child_by_name(parent, child_name):
    return next((child['children'][0]['name'] for child in parent['children'] if child['name'] == child_name), None)
def detect_update_image_tag(MI):
    refactorings = []

    for pair in MI:
        i_1, i_2 = pair
        if i_1['name'] == 'FROM' and i_2['name'] == 'FROM':
            image_name_1 = get_child_by_name(i_1, 'image_name')
            image_name_2 = get_child_by_name(i_2, 'image_name')

            tag_1 = get_child_by_name(i_1, 'image_tag')
            tag_2 = get_child_by_name(i_2, 'image_tag')

            if image_name_1 == image_name_2 and tag_1 != tag_2:
                refactorings.append((image_name_1, tag_1, tag_2))

    return refactorings
def detect_update_base_image(MS, MI, UI_1, UI_2):
    refactorings = []

    for pair in MS:
        s1, s2 = pair

        old_from_instr = next((inst for inst in s1 if inst['name'] == 'FROM'), None)
        new_from_instr = next((inst for inst in s2 if inst['name'] == 'FROM'), None)

        if not old_from_instr or not new_from_instr:
            continue

        old_image_name = get_child_by_name(old_from_instr, 'image_name')
        new_image_name = get_child_by_name(new_from_instr, 'image_name')

        if old_image_name != new_image_name:
            refactorings.append((old_image_name, new_image_name))
            exists_in_MI = any(item for item in MI if item[0] == old_from_instr and item[1] == new_from_instr)
            updated_from_instr = copy.deepcopy(new_from_instr)
            updated_from_instr['children'][0]['children'][0]['name'] = old_image_name
            if exists_in_MI:
                new_MI = []
                for item in MI:
                    if item[0] == old_from_instr:
                        new_MI.append((old_from_instr, updated_from_instr))
                    else:
                        new_MI.append(item)
                MI[:] = new_MI
            else:
                if old_from_instr in UI_1:
                    UI_1.remove(old_from_instr)
                if new_from_instr in UI_2:
                    UI_2.remove(new_from_instr)
                MI.append((old_from_instr, updated_from_instr))

    return refactorings
def detect_rename_image_alias(MI):
    refactorings = []
    for pair in MI:
        i_1, i_2 = pair
        if i_1['name'] == 'FROM' and i_2['name'] == 'FROM':
            image_name_1 = get_child_by_name(i_1, 'image_name')
            image_name_2 = get_child_by_name(i_2, 'image_name')

            alias_1 = get_child_by_name(i_1, 'image_alias')
            alias_2 = get_child_by_name(i_2, 'image_alias')

            if image_name_1 == image_name_2 and alias_1 != alias_2:
                if alias_1 is None:
                    refactorings.append(("Add Alias", alias_1, alias_2))
                else:
                    refactorings.append(("Rename Alias", alias_1, alias_2))

    return refactorings

def detect_inline_run_instructions(MS, MI, UI_1):
    refactorings = []
    new_matched_instructions = []
    for s1, s2 in MS:
        for i1, i2 in MI:
            if i1 in s1 and i2 in s2 and i1['name'] == i2['name'] == 'RUN':
                i1_commands = set()
                for command in i1['children']:
                    for child in command['children']:
                        i1_commands.add(child['name'])

                i2_commands = set()
                for command in i2['children']:
                    for child in command['children']:
                        i2_commands.add(child['name'])
                related_instr = [i1]

                for i3 in UI_1[:]:  
                    if i3 in s1 and i3['name'] == 'RUN':
                        i3_commands = set()
                        for command in i3['children']:
                            for child in command['children']:
                                i3_commands.add(child['name'])
                        
                        if (i2_commands.intersection(i3_commands) and 
                            i1_commands.intersection(i3_commands) != i2_commands.intersection(i3_commands)):
                            
                            related_instr.append(i3)
                            new_matched_instructions.append((i3, i2))
                            
                            UI_1.remove(i3)

                if related_instr[1:]:
                    refactorings.append((i2, related_instr))
    MI.extend(new_matched_instructions)

    return refactorings

def reorder_instructions(shared_instructions, stage):
    reordered_instructions = []
    for instr in stage:
        count = shared_instructions.count(instr)
        
        reordered_instructions.extend([instr] * count)
    
    return reordered_instructions

def detect_sort_instructions(MS, MI):
    refactorings = []

    for s1, s2 in MS:
        shared_instructions1 = []
        shared_instructions2 = []

        for idx, (i1, i2) in enumerate(MI):
            if i1 in s1 and i2 in s2:
                shared_instructions1.append(i1)
                shared_instructions2.append(i2)

        ordered_shared_instructions1 = reorder_instructions(shared_instructions1,s1)
        ordered_shared_instructions2 = reorder_instructions(shared_instructions2,s2)
        pairs_to_delete = set()
        for idx, (i1, i2) in enumerate(zip(ordered_shared_instructions1, ordered_shared_instructions2)):
            if (i1, i2) in MI:
                pairs_to_delete.add(idx)

        ordered_shared_instructions1 = [i for j, i in enumerate(ordered_shared_instructions1) if j not in pairs_to_delete]
        ordered_shared_instructions2 = [i for j, i in enumerate(ordered_shared_instructions2) if j not in pairs_to_delete]
    
        if ordered_shared_instructions1 and ordered_shared_instructions2:
            refactorings.append((ordered_shared_instructions1, ordered_shared_instructions2))

    return refactorings


def find_dependencies(stage):
    dependencies = []

    if isinstance(stage, list):
        for item in stage:
            dependencies.extend(find_dependencies(item))
    elif 'name' in stage and stage['name'] == 'dependency':
        dependencies.append(stage)
        if 'children' in stage:
            for child in stage['children']:
                dependencies.extend(find_dependencies(child))
    return dependencies


def detect_extract_stage_refactoring(MS, US_2):
    extracted_stages = []
    for s1, s2 in MS:
        s2_dependencies = find_dependencies(s2)

        for s3 in US_2[:]:  
            s3_dependencies = find_dependencies(s3)
            for dep in s2_dependencies:
                parts = dep["children"][0]["children"][0]["name"].strip('[]').split(', ')

                if len(parts) > 1:
                    first_number = parts[0]
                    second_number = parts[1]
                inverse_dep = ''
                if dep["children"][0]["name"] == 'builder_consumer':
                    inverse_dep = {'name': 'dependency', 'children': [{'name': 'consumer_builder', 'children': [{'name': f'[{second_number}, {first_number}]', 'children': []}]}]}
                elif dep["children"][0]["name"] == 'consumer_builder':
                    inverse_dep = {'name': 'dependency', 'children': [{'name': 'builder_consumer', 'children': [{'name': f'[{second_number}, {first_number}]', 'children': []}]}]}
                if inverse_dep in s3_dependencies:
                    extracted_stages.append((s2, s3))
                    US_2.remove(s3)  
    return extracted_stages

def detect_inline_stage_refactoring(MS, US_1):
    inlined_stages = []
    for s1, s2 in MS:
        s1_dependencies = find_dependencies(s1)

        for s3 in US_1[:]:  
            s3_dependencies = find_dependencies(s3)
            for dep in s1_dependencies:
                parts = dep["children"][0]["children"][0]["name"].strip('[]').split(', ')

                if len(parts) > 1:
                    first_number = parts[0]
                    second_number = parts[1]
                inverse_dep = ''
                if dep["children"][0]["name"] == 'builder_consumer':
                    inverse_dep = {'name': 'dependency', 'children': [{'name': 'consumer_builder', 'children': [{'name': f'[{second_number}, {first_number}]', 'children': []}]}]}
                elif dep["children"][0]["name"] == 'consumer_builder':
                    inverse_dep = {'name': 'dependency', 'children': [{'name': 'builder_consumer', 'children': [{'name': f'[{second_number}, {first_number}]', 'children': []}]}]}
                if inverse_dep in s3_dependencies:
                    inlined_stages.append((s1, s3))
                    US_1.remove(s3)  
    return inlined_stages

def match(A1, B1 ,A2, B2):
    C1 = []
    C2 = []
    A1, A2, C1 = match_components_round1(A1, A2, C1)
    A1, A2, C1 = match_components_round2(A1, A2, C1,"instruction")
    B1, B2, C2 = match_components_round1(B1, B2, C2)
    B1, B2, C2 = match_components_round2(B1, B2, C2, "stage", C1)
    return C2

def detect_move_stage(UI_1,  US_1,current_dockerfile_path, info):
    moved_stages = []
    for dockerfile_path, matching_info in info.items():
        if dockerfile_path == current_dockerfile_path:
            continue
        other_UI_2 = matching_info["UI_2"]
        other_US_2 = matching_info["US_2"]
        matched_stages = match(UI_1,  US_1, other_UI_2, other_US_2)  
        for s1 in matched_stages:
            moved_stages.append((dockerfile_path, s1))

    return moved_stages

def detect_refactorings(state,temp_repo_path, dockerfile_path_local, info):
    dockerfile_path_local = temp_repo_path + dockerfile_path_local
    matching_info = info[dockerfile_path_local]
    
    if state=="new":
        return None

    MI = matching_info["MI"]
    MS = matching_info["MS"]
    UI_1 = matching_info["UI_1"]
    UI_2 = matching_info["UI_2"]
    US_1 = matching_info["US_1"]
    US_2 = matching_info["US_2"]

    refactorings = {}
    
    refactorings["new_env_variables"] = detect_added_instructions(UI_2, 'ENV', 'key')
    refactorings["new_arg_instructions"] = detect_added_instructions(UI_2, 'ARG', 'name')
    refactorings["replace_add_with_copy"] = detect_replace_add_with_copy(MI, MS)
    refactorings["update_image_tag"] = detect_update_image_tag(MI)
    
    refactorings["update_base_image"] = detect_update_base_image(MS,MI,UI_1,UI_2)
    
    refactorings["rename_image"] = detect_rename_image_alias(MI)

    refactorings["inline_run_instructions"] = detect_inline_run_instructions(MS, MI, UI_1)
 
    refactorings["extract_run_instructions"] = detect_extract_run_instructions(UI_1, UI_2, MS)

    refactorings["sort_instructions"] = detect_sort_instructions(MS, MI)

    refactorings["extract_stage"] = detect_extract_stage_refactoring(MS, US_2)
    refactorings["inline_stage_refactoring "] = detect_inline_stage_refactoring(MS, US_1)
    
    refactorings["move_stage"] = detect_move_stage(UI_1,  US_1,dockerfile_path_local, info)
    return refactorings 

def custom_serializer(obj):
    if isinstance(obj, set):
        return {'_python_type': 'set', 'items': list(obj)}
    raise TypeError
def extract_matching_info(repo, commit_hash, temp_repo_path, dataset, renamed):
    commit = repo.commit(commit_hash)
    dockerfiles_info = {}
    parent_commit = commit.parents[0] if commit.parents else None

    for entry in dataset:
        dockerfile_path_local = temp_repo_path + entry['path']

        if entry['state'] == "new":
            repo.git.checkout(commit, f=True)
            try:
                with open(dockerfile_path_local, 'r') as f:
                    dockerfile_content2 = f.read()
                    tree2 = get_EAST(preprocess(dockerfile_content2, renamed), temp_repo_path, dockerfile_path_local)
                    dockerfiles_info[dockerfile_path_local] = {
                        "MI": [], "MS": [], "UI_1": [], "UI_2": extract_instructions(tree2), "US_1": [], "US_2": extract_stages(tree2)
                    }
            except FileNotFoundError:
                continue  

        elif entry['state'] == "modified":
            repo.git.checkout(parent_commit, f=True)
            try:
                with open(dockerfile_path_local, 'r') as f:
                    dockerfile_content1 = f.read()
                    tree1 = get_EAST(preprocess(dockerfile_content1, renamed), temp_repo_path, dockerfile_path_local)
            except FileNotFoundError:
                continue 
            
            repo.git.checkout(commit, f=True)
            try:
                with open(dockerfile_path_local, 'r') as f:
                    dockerfile_content2 = f.read()
                    tree2 = get_EAST(preprocess(dockerfile_content2, renamed), temp_repo_path, dockerfile_path_local)
            except FileNotFoundError:
                continue 
            
            MI, UI_1, UI_2, MS, US_1, US_2 = match_trees(tree1, tree2)
            dockerfiles_info[dockerfile_path_local] = {
                "MI": MI, "UI_1": UI_1, "UI_2": UI_2, "MS": MS, "US_1": US_1, "US_2": US_2
            }

        print(f'Processed Dockerfile: {dockerfile_path_local}')

    return dockerfiles_info

def process_row_commit(temp_repo_path, row, matching_info):
    dockerfile_path_local = row['path']
    state = row['state']
    try:
        output_data = detect_refactorings(state,temp_repo_path, dockerfile_path_local, matching_info)
        if all(not value for value in output_data.values()):
            return None
    except Exception as e:
        return None

    return [dockerfile_path_local, output_data]

def generate_dockerfile_dataset_commit(repo, commit_hash):
    dataset = []
    
    commit = repo.commit(commit_hash)
    parent_commit = commit.parents[0] if commit.parents else None
    renamed_files = {item.a_path: item.b_path for item in commit.diff(parent_commit) if item.renamed} if parent_commit else {}

    for diff in commit.diff(parent_commit, create_patch=True):
        file_path = diff.a_path

        if file_path and 'dockerfile' in file_path.split('/')[-1].lower():
            if diff.b_path is None:
                state = "new"  
            else:
                state = "modified" 

            dataset.append({
                "path": '/' + file_path,
                "state": state
            })

    return dataset,renamed_files

def generate_dockerfile_dataset(repo):
    dataset = []
    for commit in repo.iter_commits():
        dockerfile_changed = False
        for parent in commit.parents:
            diffs = commit.diff(parent)
            for diff in diffs:
                path_elements = diff.b_path.split('/')
                if 'dockerfile' in path_elements[-1].lower():
                    dockerfile_changed = True
                    
                    break
            if dockerfile_changed:
                break
        if dockerfile_changed:
            dataset.append({
                        
                        "commithash": commit.hexsha[:7]
                        
                    })
    return dataset
def process_row(repo,temp_repo_path, row,path):
    commit = row['commithash']
    outputs = []
    try:
        dataset,renamed = generate_dockerfile_dataset_commit(repo, commit)
        df = pd.DataFrame(dataset)
        matching_info = extract_matching_info(repo, commit, temp_repo_path, dataset,renamed)
         
        for _, row in tqdm(df.iterrows(), total=df.shape[0]):
            if path: 
                dockerfile_path_local = row['path']
                if dockerfile_path_local==path:
                    output = process_row_commit(temp_repo_path, row, matching_info)
                    if output:
                        outputs.append(output)
            
            else:
                output = process_row_commit(temp_repo_path, row, matching_info)
                if output:
                    outputs.append(output)
            
    except Exception as e:
        return None
    if outputs:
        return [commit,outputs]
    else: 
        return None
 
def count_refactorings_and_save_to_json(data, json_file_path):
    refactorings_per_commit = {}
    total_refactorings = {}

    for commit in data:
        commit_hash = commit[0]
        commit_data = commit[1]
        refactorings_per_commit[commit_hash] = {}

        for dockerfile in commit_data:
            dockerfile_refactorings = dockerfile[1]
            for refactoring_type, refactoring_list in dockerfile_refactorings.items():
                if refactoring_list:
                    count = len(refactoring_list)
                    refactorings_per_commit[commit_hash].setdefault(refactoring_type, 0)
                    refactorings_per_commit[commit_hash][refactoring_type] += count
                    total_refactorings.setdefault(refactoring_type, 0)
                    total_refactorings[refactoring_type] += count

    output_data = {
        "commit_refactorings": refactorings_per_commit,
        "total_refactorings": total_refactorings
    }

    with open(json_file_path, 'w') as file:
        json.dump(output_data, file, indent=4)

if __name__ == "__main__":
    outputs = []
    parser = argparse.ArgumentParser(description="Process a GitHub repository.")
    parser.add_argument("github_repo", type=str, help="GitHub repository URL")
    parser.add_argument("--commit", type=str, help="Specific commit hash", default=None)
    parser.add_argument("--path", type=str, help="Specific path in the repository", default=None)

    args = parser.parse_args()

    github_repo = args.github_repo
    specific_commit = args.commit
    specific_path = args.path 
    if specific_path and (not specific_path.startswith('/')):
        specific_path = '/' + specific_path    
    
    github_repo = "https://github.com/" + github_repo
    print('github_repo',github_repo)
    index = github_repo.split('/')[-1]
    temp_repo_path = f"Cloned_Repo/{index}"
    if os.path.exists(temp_repo_path):
        set_rw_and_execute(temp_repo_path, 0o777)
        shutil.rmtree(temp_repo_path)
	
    repo = git.Repo.clone_from(github_repo, temp_repo_path)
    if not specific_commit:
        dataset_commits=generate_dockerfile_dataset(repo)
    else:
        dataset_commits=[{"commithash": specific_commit[:7]}]
    df = pd.DataFrame(dataset_commits)
    for _, row in tqdm(df.iterrows(), total=df.shape[0]):
        output = process_row(repo,temp_repo_path, row,specific_path)
        if output: 
            outputs.append(output)
            print(f'Processed Commit: {output[0]}')
    with open(f'Results_{index}.json', 'w') as file:
        json.dump(outputs, file, indent=4, default=custom_serializer)
    
    json_file_path = f'Refactorings_Stats_{index}.json'
    count_refactorings_and_save_to_json(outputs, json_file_path)

    
def process_github_repo(github_repo, specific_commit=None, specific_path=None):
    github_repo = "https://github.com/" + github_repo
    print('Processing', github_repo)
    index = github_repo.split('/')[-1]
    temp_repo_path = f"repo/{specific_commit}"
    
    if os.path.exists(temp_repo_path):
        set_rw_and_execute(temp_repo_path, 0o777)
        shutil.rmtree(temp_repo_path)
    
    repo = git.Repo.clone_from(github_repo, temp_repo_path)
    outputs = []

    if not specific_commit:
        dataset_commits = generate_dockerfile_dataset(repo)
    else:
        dataset_commits = [{"commithash": specific_commit[:7]}]
    
    df = pd.DataFrame(dataset_commits)

    for _, row in tqdm(df.iterrows(), total=df.shape[0]):
        output = process_row(repo, temp_repo_path, row, specific_path)
        if output:
            outputs.append(output)
            print(f'Processed Commit: {output[0]}')
    
    with open(f'Results{index}.json', 'w') as file:
        json.dump(outputs, file, indent=4, default=custom_serializer)
    
  
    return outputs[0][1]

