import argparse
import sys

from opclash_cli import __brand__, __brand_banner__, __version__
from opclash_cli.commands.doctor import config as doctor_config
from opclash_cli.commands.doctor import logs as doctor_logs
from opclash_cli.commands.doctor import network as doctor_network
from opclash_cli.commands.doctor import runtime as doctor_runtime
from opclash_cli.commands.init import check_backends
from opclash_cli.commands.init import mask_secret, show_config, write_config
from opclash_cli.commands.init import check_backends
from opclash_cli.commands.nodes import (
    group as node_group,
    groups as nodes_groups,
    providers as nodes_providers,
    speedtest as nodes_speedtest,
    switch as switch_node,
)
from opclash_cli.commands.service import logs as service_logs
from opclash_cli.commands.service import reload as service_reload
from opclash_cli.commands.service import restart as service_restart
from opclash_cli.commands.service import status as service_status
from opclash_cli.commands.subscription import (
    add_subscription,
    disable_subscription,
    enable_subscription,
    current_config,
    list_subscriptions,
    remove_subscription,
    rename_subscription,
    switch_config,
    update_subscription,
)
from opclash_cli.errors import CliError
from opclash_cli.local_config import config_exists, config_path
from opclash_cli.output import emit, fail, ok


_MUTATING_COMMANDS = {
    "init",
    "nodes switch",
    "subscription add",
    "subscription remove",
    "subscription enable",
    "subscription disable",
    "subscription rename",
    "subscription update",
    "subscription switch",
    "service reload",
    "service restart",
}


def _add_mutation_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--yes", action="store_true", help="skip interactive confirmation")
    parser.add_argument("--dry-run", action="store_true", help="show planned action without executing")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opclash_cli",
        description="Remote OpenClash management CLI",
    )
    parser.add_argument("--version", action="store_true", help="print plain version banner")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="write or inspect local connection config",
        description="Write or inspect local connection config.",
    )
    _add_mutation_flags(init_parser)
    init_parser.add_argument("--controller-url", help="Clash controller URL")
    init_parser.add_argument("--controller-secret", help="Clash controller secret")
    init_parser.add_argument("--luci-url", help="LuCI RPC base URL")
    init_parser.add_argument("--luci-username", help="LuCI username")
    init_parser.add_argument("--luci-password", help="LuCI password")
    init_subparsers = init_parser.add_subparsers(dest="init_command")
    init_subparsers.add_parser("show", help="show masked local config", description="Show masked local config.")

    nodes_parser = subparsers.add_parser(
        "nodes",
        help="inspect nodes, groups, and switch targets",
        description="Inspect nodes, groups, and switch targets.",
    )
    nodes_subparsers = nodes_parser.add_subparsers(dest="nodes_command")
    nodes_subparsers.add_parser("groups", help="list proxy groups", description="List proxy groups.")
    nodes_subparsers.add_parser("providers", help="list providers", description="List providers.")
    speedtest_parser = nodes_subparsers.add_parser(
        "speedtest",
        help="run Clash speedtest and sort results",
        description="Run Clash speedtest and sort results.",
    )
    speedtest_parser.add_argument("--group", help="limit speedtest to one proxy group")
    speedtest_parser.add_argument("--limit", type=int, default=10, help="max number of results to return")
    speedtest_parser.add_argument("--url", default="https://www.gstatic.com/generate_204", help="probe URL")
    speedtest_parser.add_argument("--timeout", type=int, default=5000, help="per-node timeout in milliseconds")
    group_parser = nodes_subparsers.add_parser("group", help="show one proxy group", description="Show one proxy group.")
    group_parser.add_argument("--name", required=True, help="proxy group name")
    switch_parser = nodes_subparsers.add_parser(
        "switch",
        help="switch one proxy group target",
        description="Switch one proxy group target.",
    )
    _add_mutation_flags(switch_parser)
    switch_parser.add_argument("--group", required=True, help="proxy group name")
    switch_parser.add_argument("--target", required=True, help="target node name")

    subscription_parser = subparsers.add_parser(
        "subscription",
        help="manage subscriptions and config switching",
        description="Manage subscriptions and config switching.",
    )
    subscription_subparsers = subscription_parser.add_subparsers(dest="subscription_command")
    subscription_subparsers.add_parser("list", help="list subscriptions", description="List subscriptions.")
    subscription_subparsers.add_parser("current", help="show current config path", description="Show current config path.")
    add_parser = subscription_subparsers.add_parser("add", help="add subscription", description="Add subscription.")
    _add_mutation_flags(add_parser)
    add_parser.add_argument("--name", required=True, help="subscription name")
    add_parser.add_argument("--url", required=True, help="subscription URL")
    remove_parser = subscription_subparsers.add_parser(
        "remove",
        help="remove subscription and archive locally",
        description="Remove subscription and archive locally.",
    )
    _add_mutation_flags(remove_parser)
    remove_parser.add_argument("--name", required=True, help="subscription name")
    enable_parser = subscription_subparsers.add_parser(
        "enable",
        help="enable subscription updates",
        description="Enable subscription updates.",
    )
    _add_mutation_flags(enable_parser)
    enable_parser.add_argument("--name", required=True, help="subscription name")
    disable_parser = subscription_subparsers.add_parser(
        "disable",
        help="disable subscription updates",
        description="Disable subscription updates.",
    )
    _add_mutation_flags(disable_parser)
    disable_parser.add_argument("--name", required=True, help="subscription name")
    rename_parser = subscription_subparsers.add_parser(
        "rename",
        help="rename subscription",
        description="Rename subscription.",
    )
    _add_mutation_flags(rename_parser)
    rename_parser.add_argument("--name", required=True, help="current subscription name")
    rename_parser.add_argument("--to", required=True, help="new subscription name")
    update_parser = subscription_subparsers.add_parser(
        "update",
        help="update subscriptions or one config",
        description="Update subscriptions or one config.",
    )
    _add_mutation_flags(update_parser)
    update_target_group = update_parser.add_mutually_exclusive_group()
    update_target_group.add_argument("--name", help="subscription name")
    update_target_group.add_argument("--config", help="full config path on remote host")
    configs_parser = subscription_subparsers.add_parser(
        "configs",
        help="list remote config files",
        description="List remote config files.",
    )
    configs_parser.add_argument("--directory", default="/etc/openclash/config", help="remote config directory")
    switch_parser = subscription_subparsers.add_parser(
        "switch",
        help="switch active config file",
        description="Switch active config file.",
    )
    _add_mutation_flags(switch_parser)
    switch_parser.add_argument("--config", required=True, help="full config path on remote host")

    service_parser = subparsers.add_parser(
        "service",
        help="inspect and control OpenClash service",
        description="Inspect and control OpenClash service.",
    )
    service_subparsers = service_parser.add_subparsers(dest="service_command")
    service_subparsers.add_parser("status", help="show service status", description="Show service status.")
    reload_parser = service_subparsers.add_parser("reload", help="reload service", description="Reload service.")
    _add_mutation_flags(reload_parser)
    restart_parser = service_subparsers.add_parser("restart", help="restart service", description="Restart service.")
    _add_mutation_flags(restart_parser)
    service_subparsers.add_parser("logs", help="show remote openclash log", description="Show remote openclash log.")

    init_subparsers.add_parser("check", help="check controller and LuCI connectivity", description="Check controller and LuCI connectivity.")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="run local diagnostics",
        description="Run local diagnostics.",
    )
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command")
    doctor_subparsers.add_parser("network", help="check local network basics", description="Check local network basics.")
    doctor_subparsers.add_parser("runtime", help="check runtime environment", description="Check runtime environment.")
    doctor_subparsers.add_parser("config", help="check local config file", description="Check local config file.")
    doctor_logs_parser = doctor_subparsers.add_parser("logs", help="show local operation logs", description="Show local operation logs.")
    doctor_logs_parser.add_argument("--limit", type=int, default=20, help="number of log entries to show")

    subparsers.add_parser("version", help="show structured version info", description="Show structured version info.")
    completion_parser = subparsers.add_parser("completion", help="generate shell completion script", description="Generate shell completion script.")
    completion_parser.add_argument("shell", choices=["bash", "zsh"], help="target shell")

    return parser


def _command_name(args: argparse.Namespace) -> str:
    if args.command == "init":
        return "init" if args.init_command is None else f"init {args.init_command}"
    if args.command == "nodes":
        return f"nodes {args.nodes_command}"
    if args.command == "subscription":
        return f"subscription {args.subscription_command}"
    if args.command == "service":
        return f"service {args.service_command}"
    if args.command == "doctor":
        return f"doctor {args.doctor_command}"
    if args.command == "completion":
        return "completion"
    if args.command == "version":
        return "version"
    return args.command or "unknown"


def _stdin_isatty() -> bool:
    return sys.stdin.isatty()


def _version_payload() -> dict:
    return {
        "brand": __brand__,
        "version": __version__,
        "python": sys.version.split()[0],
        "config_path": str(config_path()),
    }


def _plain_version_banner() -> str:
    return f" /\\_/\\\\\n( o.o )  opclash_cli {__version__}\n > ^ <"


def _completion_script(shell: str) -> str:
    if shell == "bash":
        return """_opclash_cli_complete() {
  local cur prev words cword
  _init_completion || return
  case "${COMP_WORDS[1]}" in
    nodes)
      COMPREPLY=( $(compgen -W "groups providers group switch speedtest" -- "$cur") )
      ;;
    subscription)
      COMPREPLY=( $(compgen -W "list current add update configs switch remove enable disable rename" -- "$cur") )
      ;;
    service)
      COMPREPLY=( $(compgen -W "status reload restart logs" -- "$cur") )
      ;;
    doctor)
      COMPREPLY=( $(compgen -W "network runtime config logs" -- "$cur") )
      ;;
    completion)
      COMPREPLY=( $(compgen -W "bash zsh" -- "$cur") )
      ;;
    *)
      COMPREPLY=( $(compgen -W "init nodes subscription service doctor version completion" -- "$cur") )
      ;;
  esac
}
complete -F _opclash_cli_complete opclash_cli
"""
    return """#compdef opclash_cli

_opclash_cli() {
  local -a commands
  commands=(
    'init:initialize local config'
    'nodes:node operations'
    'subscription:subscription operations'
    'service:service operations'
    'doctor:diagnostics'
    'version:show version'
    'completion:generate shell completion'
  )
  _arguments '1:command:->command' '*::arg:->args'
  case $state in
    command)
      _describe 'command' commands
      ;;
    args)
      case $words[2] in
        nodes)
          _values 'nodes commands' groups providers group switch speedtest
          ;;
        subscription)
          _values 'subscription commands' list current add update configs switch remove enable disable rename
          ;;
        service)
          _values 'service commands' status reload restart logs
          ;;
        doctor)
          _values 'doctor commands' network runtime config logs
          ;;
        completion)
          _values 'shell' bash zsh
          ;;
      esac
      ;;
  esac
}

_opclash_cli "$@"
"""


def _dry_run_payload(args: argparse.Namespace) -> dict:
    command = _command_name(args)
    if command == "init":
        params = {
            "controller_url": args.controller_url,
            "controller_secret": mask_secret(args.controller_secret or ""),
            "luci_url": args.luci_url,
            "luci_username": args.luci_username,
            "luci_password": mask_secret(args.luci_password or ""),
            "config_path": str(config_path()),
        }
    elif command == "nodes switch":
        params = {"group": args.group, "target": args.target}
    elif command == "subscription add":
        params = {"name": args.name, "url": args.url}
    elif command == "subscription remove":
        params = {"name": args.name}
    elif command == "subscription enable":
        params = {"name": args.name}
    elif command == "subscription disable":
        params = {"name": args.name}
    elif command == "subscription rename":
        params = {"name": args.name, "to": args.to}
    elif command == "subscription update":
        params = {"name": args.name, "config": args.config}
    elif command == "subscription switch":
        params = {"config": args.config}
    else:
        params = {}
    return {"dry_run": True, "command": command, "params": params}


def _should_confirm(args: argparse.Namespace) -> bool:
    command = _command_name(args)
    return command in _MUTATING_COMMANDS and not getattr(args, "yes", False) and not getattr(args, "dry_run", False) and _stdin_isatty()


def _confirm_or_abort(args: argparse.Namespace) -> int | None:
    command = _command_name(args)
    answer = input(f"Confirm {command}? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        emit(fail(command, "CONFIRM_ABORTED", "Operation was cancelled"))
        return 1
    return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(_plain_version_banner())
        return 0

    try:
        if args.command == "version":
            emit(ok("version", _version_payload()))
            return 0

        if args.command == "completion":
            print(_completion_script(args.shell))
            return 0

        if getattr(args, "dry_run", False) and _command_name(args) in _MUTATING_COMMANDS:
            emit(ok(_command_name(args), _dry_run_payload(args)))
            return 0

        if _should_confirm(args):
            aborted = _confirm_or_abort(args)
            if aborted is not None:
                return aborted

        if args.command == "init" and args.init_command is None:
            emit(
                ok(
                    "init",
                    write_config(
                        args.controller_url,
                        args.controller_secret,
                        args.luci_url,
                        args.luci_username,
                        args.luci_password,
                    ),
                )
            )
            return 0

        if args.command == "init" and args.init_command == "show":
            if not config_exists():
                emit(fail("init show", "LOCAL_CONFIG_MISSING", "Local config file was not found"))
                return 1
            emit(ok("init show", show_config()))
            return 0

        if args.command == "init" and args.init_command == "check":
            emit(ok("init check", check_backends()))
            return 0

        if args.command == "nodes" and args.nodes_command == "groups":
            emit(ok("nodes groups", nodes_groups()))
            return 0

        if args.command == "nodes" and args.nodes_command == "providers":
            emit(ok("nodes providers", nodes_providers()))
            return 0

        if args.command == "nodes" and args.nodes_command == "group":
            emit(ok("nodes group", node_group(args.name)))
            return 0

        if args.command == "nodes" and args.nodes_command == "speedtest":
            emit(ok("nodes speedtest", nodes_speedtest(args.group, args.limit, args.url, args.timeout)))
            return 0

        if args.command == "nodes" and args.nodes_command == "switch":
            result = switch_node(args.group, args.target)
            emit(ok("nodes switch", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "list":
            emit(ok("subscription list", list_subscriptions()))
            return 0

        if args.command == "subscription" and args.subscription_command == "current":
            emit(ok("subscription current", current_config()))
            return 0

        if args.command == "subscription" and args.subscription_command == "configs":
            from opclash_cli.commands.subscription import config_files

            emit(ok("subscription configs", config_files(args.directory)))
            return 0

        if args.command == "subscription" and args.subscription_command == "add":
            result = add_subscription(args.name, args.url)
            emit(ok("subscription add", {"subscription": result["subscription"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "remove":
            result = remove_subscription(args.name)
            emit(ok("subscription remove", {"removed": result["removed"], "archive": result["archive"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "enable":
            result = enable_subscription(args.name)
            emit(ok("subscription enable", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "disable":
            result = disable_subscription(args.name)
            emit(ok("subscription disable", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "rename":
            result = rename_subscription(args.name, args.to)
            emit(ok("subscription rename", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
            return 0

        if args.command == "subscription" and args.subscription_command == "update":
            result = update_subscription(args.name, args.config)
            emit(
                ok(
                    "subscription update",
                    {
                        "target": result["target"],
                        "items": result["items"],
                        "summary": result["summary"],
                        "before": result["before"],
                        "after": result["after"],
                        "suggested_commands": result["suggested_commands"],
                    },
                    audit=result["audit"],
                )
            )
            return 0

        if args.command == "subscription" and args.subscription_command == "switch":
            result = switch_config(args.config)
            emit(ok("subscription switch", {"before": result["before"], "after": result["after"]}, audit=result["audit"]))
            return 0

        if args.command == "service" and args.service_command == "status":
            emit(ok("service status", service_status()))
            return 0

        if args.command == "service" and args.service_command == "reload":
            result = service_reload()
            emit(ok("service reload", {"result": result["result"]}, audit=result["audit"]))
            return 0

        if args.command == "service" and args.service_command == "restart":
            result = service_restart()
            emit(ok("service restart", {"result": result["result"]}, audit=result["audit"]))
            return 0

        if args.command == "service" and args.service_command == "logs":
            emit(ok("service logs", service_logs()))
            return 0

        if args.command == "doctor" and args.doctor_command == "network":
            emit(ok("doctor network", doctor_network()))
            return 0

        if args.command == "doctor" and args.doctor_command == "runtime":
            emit(ok("doctor runtime", doctor_runtime()))
            return 0

        if args.command == "doctor" and args.doctor_command == "config":
            emit(ok("doctor config", doctor_config()))
            return 0

        if args.command == "doctor" and args.doctor_command == "logs":
            emit(ok("doctor logs", doctor_logs(args.limit)))
            return 0
    except CliError as error:
        emit(fail(_command_name(args), error.code, error.message, error.details))
        return 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
