from anytree import Node
import json
from dockerfile_parse import DockerfileParser
import os
from pathlib import Path


def variableExists(x):
    if '$' in x:
        begin = x.find('$')
        end = x[begin:].find('}')
        variable = x[begin:end + 1]
        return variable, begin, end
    return '', 0, 0


def searchPosition(x, y):
    variable, begin, end = variableExists(x)
    pos = x.find(y)
    if y in x:
        if variable:
            old = pos
            while (pos in range(begin, end)) and (pos >= old):
                old = pos
                pos = x[pos + len(y):].find(y)
                if (pos != -1):
                    pos += old + len(y)
            return -1 if (pos < old) else pos
        return pos
    return -1


def parse_image_parts(y):
    pos_alt = searchPosition(y, '@')
    if pos_alt != -1:
        image_part1 = y[:pos_alt]
        image_part2 = y[pos_alt + 1:]
    else:
        image_part1, image_part2 = y, None
    return image_part1, image_part2


def parse_image_name_and_tag(image_part1):
    pos_2points = searchPosition(image_part1, ':')
    pos_as = searchPosition(image_part1, ' AS ')
    if pos_as == -1:
        pos_as = searchPosition(image_part1, ' as ')
    if pos_as != -1:
        image_part1 = image_part1[:pos_as]

    if pos_2points != -1 and (pos_as == -1 or pos_2points < pos_as):
        image_name = image_part1[:pos_2points]
        image_tag = image_part1[pos_2points + 1:]

    else:
        image_name = image_part1
        image_tag = None

    return image_name, image_tag


def parse_digest_and_alias(image_part2):
    pos_as = searchPosition(image_part2, ' AS ')
    if pos_as == -1:
        pos_as = searchPosition(image_part2, ' as ')
    if pos_as != -1:
        image_alias = image_part2[pos_as + 4:]
        image_digest = image_part2[:pos_as]
    else:
        image_alias = None
        image_digest = image_part2
    return image_digest, image_alias


def parse_alias(y):
    if y is None:
        return None

    pos_as = searchPosition(y, ' AS ')
    if pos_as == -1:
        pos_as = searchPosition(y, ' as ')
    return (y[pos_as + 4:], pos_as) if pos_as != -1 else (None, -1)


def handle_from(y, x, nb_stage):
    image_part1, image_part2 = parse_image_parts(y)
    image_name, image_tag = parse_image_name_and_tag(image_part1)
    image_digest, image_alias = None, None

    if image_part2:
        colons = [pos for pos, char in enumerate(image_part2) if char == ':']
        if len(colons) > 1:
            image_digest = image_part2[:colons[-1]]
            image_tag = image_part2[colons[-1] + 1:]
            image_alias, pos_as = parse_alias(image_tag)
            if image_alias:
                image_tag = image_tag[:pos_as]
        else:
            image_digest, image_alias = parse_digest_and_alias(image_part2)
    else:
        image_alias, pos_as = parse_alias(image_part1)

    result = [nb_stage, [x, ['image_name', [image_name]]]]

    if image_tag:
        result[1].append(['image_tag', [image_tag]])
    if image_alias:
        result[1].append(['image_alias', [image_alias]])
    if image_digest:
        result[1].append(['image_digest', [image_digest]])

    return result, image_alias, image_name


def handle_env(y, x):
    key_values = []
    pairs = y.split()
    i = 0
    while i < len(pairs):
        pair = pairs[i]
        pos_equal = pair.find('=')
        if pos_equal != -1:
            key_value_pair = ['pair', ['key', [pair[:pos_equal]]], ['value', [pair[pos_equal + 1:]]]]
            key_values.append(key_value_pair)
        else:
            if i + 1 < len(pairs):
                key_value_pair = ['pair', ['key', [pair]], ['value', [pairs[i + 1]]]]
                key_values.append(key_value_pair)
                i += 1
        i += 1
    return [x, key_values]


def handle_arg(y, x):
    pos_equal = searchPosition(y, '=')
    if (pos_equal != -1):
        name = y[:pos_equal]
        value = y[pos_equal + 1:]
        return [x, ['name', [name]], ['value', [value]]]
    return [x, ['name', [y]]]


def handle_expose(y, x):
    ports = y.split()
    portlist = ['port']
    nb = 0
    for port1 in ports:
        nb = nb + 1
        pos_anti = searchPosition(port1, '/')
        if (pos_anti != -1):
            port = port1[:pos_anti]
            protocol = port1[pos_anti + 1:]
            y = [nb, ['value', [port]], ['protocol', [protocol]]]
        else:
            y = [nb, ['value', [port1]]]
        portlist.append(y)
    return [x, portlist]


def handle_user(y, x):
    parts = y.split(':')
    if len(parts) == 1:
        try:
            uid = int(parts[0])
            return [x, ['uid', [uid]]]
        except ValueError:
            return [x, ['user', [parts[0]]]]
    elif len(parts) == 2:
        try:
            uid = int(parts[0])
            gid = int(parts[1])
            return [x, ['uid', [uid]], ['gid', [gid]]]
        except ValueError:
            return [x, [
                'user', [parts[0]]], ['group', [parts[1]]]]


def is_script(filename):
    script_exts = ['.sh', '.bash', '.zsh', '.dash']
    return any(filename.endswith(ext) for ext in script_exts)


def handle_run(y, x):
    cwd = '/'
    sub_commands = [cmd.strip() for cmd in y.split('&&')]
    processed_commands = []

    for sub_command in sub_commands:
        if not sub_command.startswith('/'):
            script_path_in_container = os.path.normpath(os.path.join(cwd, sub_command))
        else:
            script_path_in_container = sub_command

        script_path = None
        for container_path, repo_path in script_dict.items():
            if script_path_in_container.startswith(container_path):
                relative_path_in_container = os.path.relpath(script_path_in_container, container_path)
                script_path = os.path.join(repo_path, relative_path_in_container)
                break

        if script_path and os.path.isfile(script_path):
            try:
                with open(script_path, 'r') as file:
                    script_content = '\n'.join(
                        line for line in file.readlines() if not line.strip().startswith('#')
                    )
                processed_commands.append(['script', [script_content]])
            except FileNotFoundError:
                processed_commands.append(['command', [sub_command]])
        else:
            processed_commands.append(['command', [sub_command]])

    return [x] + processed_commands


script_dict = {}


def normalize_path(path):
    return path.replace("\\", "/")


def handle_copy_add(y, x, stage_aliases, current_stage_number, repo_path, dockerfile_path_local):
    pos_from = searchPosition(y, '--from')
    copy_from = []
    dependency1 = []
    dependency2 = []
    if (pos_from != -1):
        pos = searchPosition(y[pos_from:], ' ')
        copy_from = y[pos_from + 7:pos]
        y = y[:pos_from] + y[pos + 1:]
        if copy_from.isdigit():
            dependency_stage_number = int(copy_from)
        else:
            dependency_stage_number = stage_aliases.get(copy_from, None)
        if dependency_stage_number is not None:
            dependency1 = ['dependency', ['consumer_builder', [(current_stage_number, dependency_stage_number)]]]
            dependency2 = ['dependency', ['builder_consumer', [(dependency_stage_number, current_stage_number)]]]

    if (y[0] == '['):
        if (y[-1] == ']'):
            pos = y.rfind(',')
            src = y[1:pos]
            dest = y[pos + 1:-1]
            dest = dest.strip()
            dest = json.dumps(dest)
            pos2 = dest.rfind('"')
            dest = dest[3:pos2 - 2]
        else:
            pos = y.rfind(' ')
            pos2 = y.rfind(']')
            src = y[1:pos2]
            dest = y[pos2 + 1:]
        files = src.split(',')
        z = "[\"" + x + "\", [\"source\", "
        ok = False
        for file in files:
            file = file.strip()
            if ok:
                z = z + ", "
            f = json.dumps(file)
            pos2 = f.rfind('"')
            z = z + "[\"" + f[3:pos2 - 2] + "\"]"
            ok = True

        z = z + "], [\"destination\", [" + json.dumps(dest) + "]]]"
    else:
        pos = y.rfind(' ')
        src = y[:pos]
        dest = y[pos + 1:]
        files = src.split()
        z = "[\"" + x + "\", [\"source\", "
        ok = False
        for file in files:
            if ok:
                z = z + ", "
            f = json.dumps(file)
            z = z + "[" + f + "]"
            ok = True
        if (pos_from != -1):
            z = z + "], [\"destination\", [" + json.dumps(dest) + "]], [\"from\", [" + json.dumps(copy_from) + "]]]"
        else:
            z = z + "], [\"destination\", [" + json.dumps(dest) + "]]]"
    for file in files:
        file = file.strip()
        if file == '.':
            file_path_in_repo = Path(dockerfile_path_local).parent

        else:
            file_path_in_repo = os.path.join(repo_path, file)
        if os.path.isdir(file_path_in_repo):
            for dirpath, dirnames, filenames in os.walk(file_path_in_repo):
                for filename in filenames:
                    if is_script(filename):
                        container_path = (os.path.join(dest, filename)).replace("\\", '/')
                        repo_script_path = os.path.join(dirpath, filename)
                        script_dict[container_path] = repo_script_path.replace("\\", '/')
        elif is_script(file):
            absolute_path_in_container = dest.replace("\\", '/')
            script_dict[absolute_path_in_container] = file_path_in_repo.replace("\\", '/')

    return json.loads(z), dependency1, dependency2


def EAST(x, temp_repo_path, dockerfile_path_local):
    dfp = DockerfileParser()
    dfp.content = x

    nb_stage = -1
    stage_aliases = {}
    current_stage = []
    stages = ["stage"]
    recorded_dependencies_consumer_builder = set()
    recorded_dependencies_builder_consumer = set()
    for instr in (dfp.structure):
        if instr['instruction'] == 'FROM':
            if current_stage:
                stages.append(current_stage)
            nb_stage += 1
            current_stage, stage_alias, stage_name = handle_from(instr['value'], instr['instruction'], nb_stage)

            if stage_name in stage_aliases:
                stage_number = stage_aliases[stage_name]
                dependency1 = ['dependency', ['consumer_builder', [(nb_stage, stage_number)]]]
                dependency2 = ['dependency', ['builder_consumer', [(stage_number, nb_stage)]]]
                if dependency1:
                    dependency_key1 = (dependency1[1][1][0][1], dependency1[1][1][0][0])
                    if dependency_key1 not in recorded_dependencies_consumer_builder:
                        current_stage.insert(1, dependency1)
                        recorded_dependencies_consumer_builder.add(dependency_key1)

                if dependency2:
                    dependency_key2 = (dependency2[1][1][0][0], dependency2[1][1][0][1])
                    if dependency_key2 not in recorded_dependencies_builder_consumer:
                        nb_stage_builder = dependency2[1][1][0][0]
                        for s in stages:
                            if isinstance(s, list):
                                if len(s) > 0 and s[0] == nb_stage_builder:
                                    s.insert(1, dependency2)
                                    break

                        recorded_dependencies_builder_consumer.add(dependency_key2)
            if stage_alias:
                stage_aliases[stage_alias] = nb_stage
            continue
        elif (instr['instruction'] == 'ENV'):
            env_entries = handle_env(instr['value'], instr['instruction'])
            for env_entry in env_entries[1]:
                current_stage.append(['ENV', env_entry[1], env_entry[2]])
            continue
        elif (instr['instruction'] == 'ARG'):
            if current_stage:
                x = handle_arg(instr['value'], instr['instruction'])
            else:
                current_stage = handle_arg(instr['value'], instr['instruction'])
                stages.append(current_stage)
                current_stage = []
                continue
        elif (instr['instruction'] == 'EXPOSE'):
            x = handle_expose(instr['value'], instr['instruction'])
        elif instr['instruction'] == 'USER':
            x = handle_user(instr['value'], instr['instruction'])

        elif (instr['instruction'] == 'RUN'):

            x = handle_run(instr['value'], instr['instruction'])

        elif (instr['instruction'] in {'COPY', 'ADD'}):
            x, dependency1, dependency2 = handle_copy_add(instr['value'], instr['instruction'], stage_aliases, nb_stage,
                                                          temp_repo_path, dockerfile_path_local)
            if dependency1:
                dependency_key1 = (dependency1[1][1][0][1], dependency1[1][1][0][0])
                if dependency_key1 not in recorded_dependencies_consumer_builder:
                    current_stage.insert(1, dependency1)
                    recorded_dependencies_consumer_builder.add(dependency_key1)

            if dependency2:
                dependency_key2 = (dependency2[1][1][0][0], dependency2[1][1][0][1])
                if dependency_key2 not in recorded_dependencies_builder_consumer:
                    nb_stage_builder = dependency2[1][1][0][0]
                    for s in stages:
                        if isinstance(s, list):
                            if len(s) > 0 and s[0] == nb_stage_builder:
                                s.insert(1, dependency2)
                                break

                    recorded_dependencies_builder_consumer.add(dependency_key2)
        elif (instr['instruction'] == 'WORKDIR'):

            x = [instr['instruction'], ['path', [instr['value']]]]

        elif (instr['instruction'] == 'ONBUILD'):
            x = [instr['instruction'], ['instruction', [instr['value']]]]
        elif (instr['instruction'] in ['ENTRYPOINT', 'CMD']):
            x = [instr['instruction'], ['command', [instr['value']]]]
        elif (instr['instruction'] == 'VOLUME'):
            x = [instr['instruction'], ['arguments', [instr['value']]]]
        else:
            continue

        if (instr['instruction'] != 'FROM') and (x):
            current_stage.append(x)
        variable = ''

    if current_stage:
        stages.append(current_stage)
    result = json.dumps(stages)
    return result


def create_node(data):
    if isinstance(data, list) and len(data) > 0:
        children = [create_node(child) for child in data[1:]]
        return Node(str(data[0]), children=children)
    else:
        return Node(str(data))


def json_to_tree(json_list):
    root = create_node(json_list)
    return root


def get_EAST(dockerfile_content, temp_repo_path, dockerfile_path_local):
    json_list = EAST(dockerfile_content, temp_repo_path, dockerfile_path_local)
    json_list = json.loads(json_list)
    tree = json_to_tree(json_list)
    return tree