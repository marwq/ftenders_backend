import json
from pathlib import Path
import sys

from jinja2 import Environment, FileSystemLoader, Template


tool_responses_path = Path(__file__).parent / 'tool_responses'
prompts_path = Path(__file__).parent / 'prompts'

tool_responses_env = Environment(loader=FileSystemLoader(tool_responses_path))
prompts_env = Environment(loader=FileSystemLoader(prompts_path))

tool_responses: dict[str, Template] = {
    file.name.removesuffix('.txt'): tool_responses_env.get_template(file.name)
    for file in tool_responses_path.iterdir()
}

prompts: dict[str, Template] = {
    file.name.removesuffix('.txt'): prompts_env.get_template(file.name)
    for file in prompts_path.iterdir()
}


if __name__ == '__main__':
    is_interactive = sys.stdin.isatty()

    if is_interactive:
        type_ = input('Choose template type:\n 1. prompt\n 2. tool_response\n> ')
    else:
        type_ = sys.argv[1] if len(sys.argv) > 1 else '1'

    if type_ == '1':
        env = prompts
    elif type_ == '2':
        env = tool_responses
    else:
        print('Incorrect choice')
        sys.exit(1)

    if is_interactive:
        template_name = input('Enter template name: ')
    else:
        template_name = sys.argv[2] if len(sys.argv) > 2 else ''
        if not template_name:
            print('Usage: cat data.json | python templates.py <1|2> <template_name>')
            sys.exit(1)

    if is_interactive:
        lines = [input('Paste json data: ')]
        while (line := input('\nPress Enter to finish ').strip()) != '':
            lines.append(line)
    else:
        lines = [line.rstrip('\n') for line in sys.stdin]

    print('\n############## RENDER ##############\n')
    print(env[template_name].render(json.loads('\n'.join(lines))))
