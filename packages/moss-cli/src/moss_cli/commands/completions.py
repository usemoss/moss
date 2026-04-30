"""moss completions command – outputs shell completion scripts."""

from __future__ import annotations

from enum import Enum

import typer


class Shell(str, Enum):
    bash = "bash"
    zsh = "zsh"


_BASH_SCRIPT = r"""# moss bash completion
# Add to ~/.bashrc:
#   eval "$(moss completions bash)"

_moss_index_names() {
    moss index list --json 2>/dev/null | python3 -c "
import sys, json
try:
    for i in json.load(sys.stdin):
        n = i.get('name', '')
        if n:
            print(n)
except Exception:
    pass
" 2>/dev/null
}

_moss() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"

    # Global options that consume the next word (value)
    local opts_with_args="--project-id -p --project-key --profile"

    # Walk COMP_WORDS to find the top-level command and subcommand,
    # skipping global option values so they aren't misidentified as commands.
    local cmd="" subcmd="" skip_next=0
    local i
    for ((i = 1; i < COMP_CWORD; i++)); do
        local w="${COMP_WORDS[i]}"
        if ((skip_next)); then
            skip_next=0
            continue
        fi
        if [[ " $opts_with_args " == *" $w "* ]]; then
            skip_next=1
            continue
        fi
        if [[ "$w" != -* ]]; then
            if [[ -z "$cmd" ]]; then
                cmd="$w"
            elif [[ -z "$subcmd" ]]; then
                subcmd="$w"
                break
            fi
        fi
    done

    local _global="--project-id -p --project-key --profile --json --verbose -v"

    case "$cmd" in
        "")
            COMPREPLY=($(compgen -W "index doc job profile query init version completions $_global" -- "$cur"))
            ;;

        index)
            case "$subcmd" in
                "")
                    COMPREPLY=($(compgen -W "create list get delete" -- "$cur"))
                    ;;
                create)
                    case "$prev" in
                        --file|-f)            COMPREPLY=($(compgen -f -- "$cur")) ;;
                        --model|-m|--poll-interval|--profile) ;;
                        *)                    COMPREPLY=($(compgen -W "--file -f --model -m --wait -w --poll-interval --profile" -- "$cur")) ;;
                    esac
                    ;;
                list)
                    case "$prev" in
                        --profile) ;;
                        *)         COMPREPLY=($(compgen -W "--profile" -- "$cur")) ;;
                    esac
                    ;;
                get)
                    case "$prev" in
                        --profile) ;;
                        *)         COMPREPLY=($(compgen -W "$(_moss_index_names) --profile" -- "$cur")) ;;
                    esac
                    ;;
                delete)
                    case "$prev" in
                        --profile) ;;
                        *)         COMPREPLY=($(compgen -W "$(_moss_index_names) --profile --confirm -y" -- "$cur")) ;;
                    esac
                    ;;
            esac
            ;;

        doc)
            case "$subcmd" in
                "")
                    COMPREPLY=($(compgen -W "add delete get" -- "$cur"))
                    ;;
                add)
                    case "$prev" in
                        --file|-f)                    COMPREPLY=($(compgen -f -- "$cur")) ;;
                        --profile|--poll-interval)    ;;
                        *)                            COMPREPLY=($(compgen -W "$(_moss_index_names) --file -f --upsert -u --wait -w --poll-interval --profile" -- "$cur")) ;;
                    esac
                    ;;
                delete)
                    case "$prev" in
                        --ids|-i|--profile|--poll-interval) ;;
                        *)                                  COMPREPLY=($(compgen -W "$(_moss_index_names) --ids -i --wait -w --poll-interval --profile" -- "$cur")) ;;
                    esac
                    ;;
                get)
                    case "$prev" in
                        --ids|-i|--profile) ;;
                        *)                  COMPREPLY=($(compgen -W "$(_moss_index_names) --ids -i --profile" -- "$cur")) ;;
                    esac
                    ;;
            esac
            ;;

        job)
            case "$subcmd" in
                "")
                    COMPREPLY=($(compgen -W "status" -- "$cur"))
                    ;;
                status)
                    case "$prev" in
                        --profile|--poll-interval) ;;
                        *)                         COMPREPLY=($(compgen -W "--wait -w --poll-interval --profile" -- "$cur")) ;;
                    esac
                    ;;
            esac
            ;;

        profile)
            case "$subcmd" in
                "")
                    COMPREPLY=($(compgen -W "list delete" -- "$cur"))
                    ;;
                delete)
                    COMPREPLY=($(compgen -W "--force -f" -- "$cur"))
                    ;;
            esac
            ;;

        query)
            case "$prev" in
                --profile|--top-k|-k|--alpha|-a|--filter) ;;
                *)                                         COMPREPLY=($(compgen -W "$(_moss_index_names) --profile --top-k -k --alpha -a --filter --cloud -c --interactive -i" -- "$cur")) ;;
            esac
            ;;

        completions)
            COMPREPLY=($(compgen -W "bash zsh" -- "$cur"))
            ;;
    esac
}

complete -F _moss moss
"""

_ZSH_SCRIPT = r"""#compdef moss

# moss zsh completion
# Add to ~/.zshrc:
#   eval "$(moss completions zsh)"
# Or source directly:
#   source <(moss completions zsh)

_moss_index_names() {
    local -a names
    names=(${(f)"$(moss index list --json 2>/dev/null | python3 -c '
import sys, json
try:
    for i in json.load(sys.stdin):
        n = i.get("name", "")
        if n:
            print(n)
except Exception:
    pass
' 2>/dev/null)"})
    _describe 'index name' names
}

_moss_commands() {
    local commands=(
        'index:Manage indexes'
        'doc:Manage documents'
        'job:Track background jobs'
        'profile:Manage auth profiles'
        'query:Query an index'
        'init:Initialize credentials'
        'version:Print version'
        'completions:Output shell completion scripts'
    )
    _describe 'command' commands
}

_moss_index_subcmds() {
    local subcmds=(
        'create:Create a new index'
        'list:List all indexes'
        'get:Get index details'
        'delete:Delete an index'
    )
    _describe 'index subcommand' subcmds
}

_moss_doc_subcmds() {
    local subcmds=(
        'add:Add documents to an index'
        'delete:Delete documents from an index'
        'get:Retrieve documents from an index'
    )
    _describe 'doc subcommand' subcmds
}

_moss_job_subcmds() {
    local subcmds=('status:Get the status of a background job')
    _describe 'job subcommand' subcmds
}

_moss_profile_subcmds() {
    local subcmds=(
        'list:List credential profiles'
        'delete:Delete a credential profile'
    )
    _describe 'profile subcommand' subcmds
}

_moss_index() {
    local context state line
    typeset -A opt_args
    _arguments -C \
        '1: :_moss_index_subcmds' \
        '*:: :->subcmd'
    case $state in
        subcmd)
            case $line[1] in
                create)
                    _arguments \
                        '(-f --file)'{-f,--file}'[Path to document file]:file:_files' \
                        '(-m --model)'{-m,--model}'[Model ID]:model:' \
                        '--profile[Credential profile]:profile:' \
                        '(-w --wait)'{-w,--wait}'[Wait for job to complete]' \
                        '--poll-interval[Seconds between status checks]:seconds:' \
                        '1:index name:'
                    ;;
                list)
                    _arguments '--profile[Credential profile]:profile:'
                    ;;
                get)
                    _arguments \
                        '--profile[Credential profile]:profile:' \
                        '1:index name:_moss_index_names'
                    ;;
                delete)
                    _arguments \
                        '--profile[Credential profile]:profile:' \
                        '(-y --confirm)'{-y,--confirm}'[Skip confirmation]' \
                        '1:index name:_moss_index_names'
                    ;;
            esac
            ;;
    esac
}

_moss_doc() {
    local context state line
    typeset -A opt_args
    _arguments -C \
        '1: :_moss_doc_subcmds' \
        '*:: :->subcmd'
    case $state in
        subcmd)
            case $line[1] in
                add)
                    _arguments \
                        '(-f --file)'{-f,--file}'[Path to document file]:file:_files' \
                        '--profile[Credential profile]:profile:' \
                        '(-u --upsert)'{-u,--upsert}'[Update existing documents]' \
                        '(-w --wait)'{-w,--wait}'[Wait for job to complete]' \
                        '--poll-interval[Seconds between status checks]:seconds:' \
                        '1:index name:_moss_index_names'
                    ;;
                delete)
                    _arguments \
                        '(-i --ids)'{-i,--ids}'[Comma-separated document IDs]:ids:' \
                        '--profile[Credential profile]:profile:' \
                        '(-w --wait)'{-w,--wait}'[Wait for job to complete]' \
                        '--poll-interval[Seconds between status checks]:seconds:' \
                        '1:index name:_moss_index_names'
                    ;;
                get)
                    _arguments \
                        '(-i --ids)'{-i,--ids}'[Comma-separated document IDs]:ids:' \
                        '--profile[Credential profile]:profile:' \
                        '1:index name:_moss_index_names'
                    ;;
            esac
            ;;
    esac
}

_moss_job() {
    local context state line
    typeset -A opt_args
    _arguments -C \
        '1: :_moss_job_subcmds' \
        '*:: :->subcmd'
    case $state in
        subcmd)
            case $line[1] in
                status)
                    _arguments \
                        '--profile[Credential profile]:profile:' \
                        '(-w --wait)'{-w,--wait}'[Poll until job completes]' \
                        '--poll-interval[Seconds between status checks]:seconds:' \
                        '1:job id:'
                    ;;
            esac
            ;;
    esac
}

_moss_profile() {
    local context state line
    typeset -A opt_args
    _arguments -C \
        '1: :_moss_profile_subcmds' \
        '*:: :->subcmd'
    case $state in
        subcmd)
            case $line[1] in
                delete)
                    _arguments \
                        '(-f --force)'{-f,--force}'[Delete without confirmation]' \
                        '1:profile name:'
                    ;;
            esac
            ;;
    esac
}

_moss_query() {
    _arguments \
        '--profile[Credential profile]:profile:' \
        '(-k --top-k)'{-k,--top-k}'[Number of results]:k:(5 10 20 50)' \
        '(-a --alpha)'{-a,--alpha}'[Semantic weight 0.0-1.0]:alpha:' \
        '--filter[Metadata filter as JSON]:filter:' \
        '(-c --cloud)'{-c,--cloud}'[Query via cloud API]' \
        '(-i --interactive)'{-i,--interactive}'[Start interactive query session]' \
        '1:index name:_moss_index_names' \
        '2:query text:'
}

_moss_completions_cmd() {
    local shells=('bash:Output bash completion script' 'zsh:Output zsh completion script')
    _describe 'shell' shells
}

_moss() {
    local context state line
    typeset -A opt_args

    _arguments -C \
        '(-p --project-id)'{-p,--project-id}'[Project ID]:project id:' \
        '--project-key[Project key]:project key:' \
        '--profile[Credential profile]:profile:' \
        '--json[Output as JSON]' \
        '(-v --verbose)'{-v,--verbose}'[Enable debug logging]' \
        '1: :_moss_commands' \
        '*:: :->subcmd'

    case $state in
        subcmd)
            case $line[1] in
                index)       _moss_index ;;
                doc)         _moss_doc ;;
                job)         _moss_job ;;
                profile)     _moss_profile ;;
                query)       _moss_query ;;
                completions) _moss_completions_cmd ;;
            esac
            ;;
    esac
}

_moss
"""


def completions_command(
    shell: Shell = typer.Argument(..., help="Shell type: bash or zsh"),
) -> None:
    """Output a shell completion script.

    Bash: eval "$(moss completions bash)"
    Zsh:  eval "$(moss completions zsh)"
    """
    if shell == Shell.bash:
        typer.echo(_BASH_SCRIPT, nl=False)
    else:
        typer.echo(_ZSH_SCRIPT, nl=False)
