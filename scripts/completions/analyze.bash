_analyze_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-f --file -i --index -a --all -p --profile --benchmark-version -e --export --history -v --verbose -b --background --db --help"

    case "${prev}" in
        -i|--index)
            local indices=$(./analyze.py --list-indices 2>/dev/null)
            COMPREPLY=( $(compgen -W "${indices}" -- ${cur}) )
            return 0
            ;;
        -p|--profile)
            local profiles=$(./analyze.py --list-profiles 2>/dev/null)
            COMPREPLY=( $(compgen -W "${profiles}" -- ${cur}) )
            return 0
            ;;
        -e|--export)
            COMPREPLY=( $(compgen -W "csv txt" -- ${cur}) )
            return 0
            ;;
        --db)
            COMPREPLY=( $(compgen -W "assets indices snapshots sectors profiles benchmarks inventory" -- ${cur}) )
            return 0
            ;;
        *)
            ;;
    esac

    if [[ ${cur} == -* ]] ; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
        return 0
    fi

    # Default to file completion for tickers or ticker files
    COMPREPLY=( $(compgen -f -- ${cur}) )
}

complete -F _analyze_completion analyze.py ./analyze.py
