from Levenshtein import distance as levenshtein_distance
import re

def normalize_whitespace(text):
    text = re.sub(r'\\$', ' ', text)
    text = re.sub(r'\\\n', ' ', text)  
    text = re.sub(r'&&', ' ', text) 
    return re.sub(r'\s+', ' ', text).strip()


def extract_subtree(node):
 
    return {
        "name": normalize_whitespace(node.name),
        "children": [extract_subtree(child) for child in node.children]
        
    }


def extract_instructions_from_node(node):

    if node.name.isdigit():
        return [extract_subtree(inst) for inst in node.children]
    else:
        return [extract_subtree(node)]

def extract_instructions(node):
 
    instructions = []

    for child in node.children:
        instructions.extend(extract_instructions_from_node(child))

    return instructions

def extract_stages(tree):
    stages = []
    current_stage = []

    for child in tree.children:
        if child.name.isdigit():
            if current_stage:
                stages.append(current_stage)
                current_stage = []
            instructions = extract_instructions_from_node(child)
            current_stage.extend(instructions)
    if current_stage:
        stages.append(current_stage)

    return stages

def match_components_round1(N1, N2, M):
    N1_copy = N1.copy() 
    for c1 in N1_copy:
        N2_copy = N2.copy()  
        for c2 in N2_copy:
            if c1 == c2:
                M.append((c1, c2))
                N1.remove(c1)
                N2.remove(c2)
                break
    return N1, N2, M

def extractLeaves(instruction):
    if not instruction['children']:
        return [instruction['name']]
    
    leaves = []
    for child in instruction['children']:
        leaves.extend(extractLeaves(child))
    return leaves

def allLeafCombinations(instruction):
    combinations = []
    for child in instruction['children']:
        for leaf in extractLeaves(child):
            combinations.append((child['name'], leaf))
    return combinations

def commonChilds(i1, i2):
    combinations_i1 = allLeafCombinations(i1)
    combinations_i2 = allLeafCombinations(i2)

    common_count = 0
    for combo1 in combinations_i1:
        for combo2 in combinations_i2:
            if combo1 == combo2:
                common_count += 1
                break

    return common_count

def uncommonChilds(i1, i2):
    combinations_i1 = allLeafCombinations(i1)
    combinations_i2 = allLeafCombinations(i2)
    
    uncommon = []
    for combo1 in combinations_i1:
        if combo1 not in combinations_i2:
            uncommon.append(combo1)
    
    return uncommon

def totalChilds(instruction):
    return len(allLeafCombinations(instruction))

def totalInstructions(c):
    return len(c)

def matchingInstructions(c1, c2, MI):
 
    count = 0
    for inst1 in c1:
        for inst2 in c2:
            if (inst1, inst2) in MI:
                count += 1
                break
    return count

def compute_distance(tuple1, tuple2):
    return sum(levenshtein_distance(str(a), str(b)) for a, b in zip(tuple1, tuple2))

def get_min_distance_pair(list1, list2):
    min_distance = float('inf')
    min_pair = None

    for tuple1 in list1:
        for tuple2 in list2:
            current_distance = compute_distance(tuple1, tuple2)
            if current_distance < min_distance:
                min_distance = current_distance
                min_pair = (tuple1, tuple2)
                
    return min_pair, min_distance

def tuple_distance(list1, list2):
    total_distance = 0
    list1_copy = list1.copy()
    list2_copy = list2.copy()
    
    while list1_copy and list2_copy:
        (tuple1, tuple2), min_distance = get_min_distance_pair(list1_copy, list2_copy)
        total_distance += min_distance
        
        list1_copy.remove(tuple1)
        list2_copy.remove(tuple2)

    for tuple_ in list1_copy + list2_copy:
        total_distance += sum(len(str(item)) for item in tuple_)

    return total_distance
def computeScore(c1, c2, type, MI=None):
    if type == "instruction":
        return commonChilds(c1, c2) / totalChilds(c2)
    else:
        return matchingInstructions(c1, c2, MI) / totalInstructions(c2)
def findBestMatch(P, type):
    
    if type == "instruction" :
        pairs_with_common_children = [pair for pair in P if len(uncommonChilds(pair[0], pair[1])) > 0 or len(uncommonChilds(pair[1], pair[0])) > 0]

        if pairs_with_common_children:
            return min(pairs_with_common_children, key=lambda x: tuple_distance(
        uncommonChilds(x[0], x[1]),uncommonChilds(x[1], x[0])))
    return P[0] 
 

def match_components_round2(N1, N2, M, type, MI=None):
    Scores = []
    for c1 in N1:
        for c2 in N2:
            score = computeScore(c1, c2, type,MI)
            if score > 0:
                Scores.append((c1, c2, score))
    while Scores:
        
        maxScorePairs = [pair for pair in Scores if pair[2] == max([x[2] for x in Scores])]

        best_match = findBestMatch(maxScorePairs, type)

        M.append((best_match[0], best_match[1]))
        N1.remove(best_match[0])
        N2.remove(best_match[1])
        Scores = [x for x in Scores if x[0] != best_match[0] and x[1] != best_match[1]]
    return N1, N2, M

def match_trees(T1, T2):
    MI = []
    MS = [] 
    UI_1 = extract_instructions(T1)
    UI_2 = extract_instructions(T2) 
    US_1 = extract_stages(T1) 
    US_2 = extract_stages(T2) 
    UI_1, UI_2, MI = match_components_round1(UI_1, UI_2, MI)
    UI_1, UI_2, MI = match_components_round2(UI_1, UI_2, MI,"instruction")
    US_1, US_2, MS = match_components_round1(US_1, US_2, MS)
    US_1, US_2, MS = match_components_round2(US_1, US_2, MS, "stage", MI)
    return MI, UI_1, UI_2, MS, US_1, US_2


def unification(dockerfile_text):
    lines = dockerfile_text.split('\n')

    default_values = {}

    processed_lines = []

    for line in lines:
        # Exclude comment lines
        if line.strip().startswith('#'):
            continue

        if line.startswith('ARG ') or line.startswith('ENV '):
            parts = line.split(None, 1)
            if len(parts) == 2:
                vars = parts[1].split()
                for var in vars:
                    var_parts = var.split('=', 1)
                    if len(var_parts) == 2:
                        var_name, var_value = var_parts
                        default_values[var_name] = var_value.strip('"').strip("'")
                    elif len(var_parts) == 1:
                        var_name = var_parts[0]
                        default_values[var_name] = ''

        for var_name, var_value in default_values.items():
            if '${' + var_name + '}' in line:
                line = line.replace('${' + var_name + '}', var_value)

        processed_lines.append(line)

    return '\n'.join(processed_lines)



def shellStriping(match):
    instruction, command = match.groups()
    command = command.replace("\\\n", " ")
    command_abstracted = ' '.join(segment for segment in command.split() if not segment.startswith('-'))
    return instruction + command_abstracted
def abstract_run_instructions(dockerfile_content):
    lines = dockerfile_content.split("\n")
    
    new_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip() 

        if line.startswith("RUN") and not line.startswith("#"):
            full_run_command = ""
            while line.endswith('\\') or not full_run_command:
                if line.endswith('\\'):
                    line = line[:-1].rstrip() 
                full_run_command += line + " "
                i += 1
                if i < len(lines):
                    line = lines[i].rstrip()
                else:
                    break
            
            full_run_command = re.sub(r'(\s+-\w+\b(?<!/))|(\s+--[\w-]+(?:=\S+)?\b(?<!/))', ' ', full_run_command)
            
            full_run_command = re.sub(r'\s+', ' ', full_run_command)
            new_lines.append(full_run_command.strip())
        else:
            if not line.endswith('\\'):  
                new_lines.append(line)
        i += 1

    abstracted_dockerfile_content = "\n".join(new_lines)

    return abstracted_dockerfile_content

def substitute_arg_env(text):
    arg_env_pattern = r'(?i)(ARG|ENV) (\w+)=(".*?"|\'.*?\'|\S+)'
    replacements = {}
    def replace_default(match):
        _, name, value = match.groups()
        replacements[name] = value.strip('"').strip("'")  
        return match.group(0)  
    
    text = re.sub(arg_env_pattern, replace_default, text)
    for name, value in replacements.items():
        text = re.sub(r'(?<!\w)\${?' + re.escape(name) + r'\}?', value, text)
    return text

def adjust_filenames(text, renamed_files):
    for old_path, new_path in renamed_files.items():
        add_copy_pattern = r'(?i)(ADD|COPY) (.*?)(\s+' + re.escape(old_path) + r')(\s|$)'
        text = re.sub(add_copy_pattern, r'\1 \2 ' + new_path + r'\4', text)
    return text

def preprocess(text, renamed_files=None):
    text = unification(text)
    run_pattern = r'(?i)(RUN\s+)([^\n\\]*(?:\\[\s\S][^\n\\]*)*)'

    text = re.sub(run_pattern, shellStriping, text)

    
    if renamed_files:
        text = adjust_filenames(text, renamed_files)
    return text
