import argparse

from opclash_cli.commands.doctor import config as doctor_config
from opclash_cli.commands.doctor import logs as doctor_logs
from opclash_cli.commands.doctor import network as doctor_network
from opclash_cli.commands.doctor import runtime as doctor_runtime
from opclash_cli.commands.init import show_config, write_config
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
    current_config,
    list_subscriptions,
    switch_config,
    update_subscription,
)
from opclash_cli.errors import CliError
from opclash_cli.local_config import config_exists
from opclash_cli.output import emit, fail, ok


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="opclash_cli")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--controller-url")
    init_parser.add_argument("--controller-secret")
    init_parser.add_argument("--luci-url")
    init_parser.add_argument("--luci-username")
    init_parser.add_argument("--luci-password")
    init_subparsers = init_parser.add_subparsers(dest="init_command")
    init_subparsers.add_parser("show")

    nodes_parser = subparsers.add_parser("nodes")
    nodes_subparsers = nodes_parser.add_subparsers(dest="nodes_command")
    nodes_subparsers.add_parser("groups")
    nodes_subparsers.add_parser("providers")
    speedtest_parser = nodes_subparsers.add_parser("speedtest")
    speedtest_parser.add_argument("--group")
    speedtest_parser.add_argument("--limit", type=int, default=10)
    speedtest_parser.add_argument("--url", default="https://www.gstatic.com/generate_204")
    speedtest_parser.add_argument("--timeout", type=int, default=5000)
    group_parser = nodes_subparsers.add_parser("group")
    group_parser.add_argument("--name", required=True)
    switch_parser = nodes_subparsers.add_parser("switch")
    switch_parser.add_argument("--group", required=True)
    switch_parser.add_argument("--target", required=True)

    subscription_parser = subparsers.add_parser("subscription")
    subscription_subparsers = subscription_parser.add_subparsers(dest="subscription_command")
    subscription_subparsers.add_parser("list")
    subscription_subparsers.add_parser("current")
    add_parser = subscription_subparsers.add_parser("add")
    add_parser.add_argument("--name", required=True)
    add_parser.add_argument("--url", required=True)
    update_parser = subscription_subparsers.add_parser("update")
    update_target_group = update_parser.add_mutually_exclusive_group()
    update_target_group.add_argument("--name")
    update_target_group.add_argument("--config")
    configs_parser = subscription_subparsers.add_parser("configs")
    configs_parser.add_argument("--directory", default="/etc/openclash/config")
    switch_parser = subscription_subparsers.add_parser("switch")
    switch_parser.add_argument("--config", required=True)

    service_parser = subparsers.add_parser("service")
    service_subparsers = service_parser.add_subparsers(dest="service_command")
    service_subparsers.add_parser("status")
    reload_parser = service_subparsers.add_parser("reload")
    restart_parser = service_subparsers.add_parser("restart")
    service_subparsers.add_parser("logs")

    init_subparsers.add_parser("check")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command")
    doctor_subparsers.add_parser("network")
    doctor_subparsers.add_parser("runtime")
    doctor_subparsers.add_parser("config")
    doctor_logs_parser = doctor_subparsers.add_parser("logs")
    doctor_logs_parser.add_argument("--limit", type=int, default=20)

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
    return args.command or "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
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
