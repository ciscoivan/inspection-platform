import ipaddress
from fastapi import APIRouter, Request, Form
from ..templating import templates

router = APIRouter(prefix="/subnet", tags=["subnet"])


def calc_ipv4(network_str: str) -> dict:
    """计算 IPv4 子网信息。"""
    try:
        net = ipaddress.IPv4Network(network_str, strict=False)
    except (ValueError, ipaddress.AddressValueError) as e:
        return {"error": f"无效的 IPv4 网段: {e}"}

    hosts = list(net.hosts())
    return {
        "cidr": str(net),
        "network": str(net.network_address),
        "netmask": str(net.netmask),
        "wildcard": str(net.hostmask),
        "broadcast": str(net.broadcast_address),
        "first_host": str(hosts[0]) if hosts else "N/A",
        "last_host": str(hosts[-1]) if hosts else "N/A",
        "total_hosts": net.num_addresses - 2 if net.num_addresses > 2 else 0,
        "total_ips": net.num_addresses,
        "prefix_len": net.prefixlen,
        "is_private": net.is_private,
        "binary_mask": ".".join(f"{int(o):08b}" for o in net.netmask.packed),
    }


def calc_subnets(network_str: str, new_prefix: int) -> dict:
    """划分 IPv4 子网。"""
    try:
        net = ipaddress.IPv4Network(network_str, strict=False)
    except (ValueError, ipaddress.AddressValueError) as e:
        return {"error": f"无效的网段: {e}"}

    if new_prefix <= net.prefixlen:
        return {"error": f"新前缀长度 ({new_prefix}) 必须大于当前前缀 ({net.prefixlen})"}

    try:
        subnets = list(net.subnets(new_prefix=new_prefix))
    except Exception as e:
        return {"error": str(e)}

    return {
        "parent": str(net),
        "new_prefix": new_prefix,
        "subnet_count": len(subnets),
        "hosts_per_subnet": subnets[0].num_addresses - 2 if subnets else 0,
        "subnets": [
            {
                "index": i + 1,
                "network": str(sn.network_address),
                "first": str(list(sn.hosts())[0]) if sn.num_addresses > 2 else str(sn.network_address),
                "last": str(list(sn.hosts())[-1]) if sn.num_addresses > 2 else str(sn.broadcast_address),
                "broadcast": str(sn.broadcast_address),
                "mask": str(sn.netmask),
            }
            for i, sn in enumerate(subnets[:128])  # 最多显示 128 个子网
        ],
    }


def calc_ipv6(network_str: str) -> dict:
    """计算 IPv6 子网信息。"""
    try:
        net = ipaddress.IPv6Network(network_str, strict=False)
    except (ValueError, ipaddress.AddressValueError) as e:
        return {"error": f"无效的 IPv6 网段: {e}"}

    # IPv6 用整数运算避免 hosts() 迭代 (prefix 太小时会 OOM)
    first = ipaddress.IPv6Address(int(net.network_address) + 1) if net.num_addresses > 2 else net.network_address
    last = ipaddress.IPv6Address(int(net.network_address) + net.num_addresses - 2) if net.num_addresses > 2 else net.network_address
    return {
        "cidr": str(net),
        "network": str(net.network_address),
        "prefix_len": net.prefixlen,
        "total_ips": str(net.num_addresses),
        "first_host": str(first),
        "last_host": str(last),
        "is_private": net.is_private,
        "is_link_local": net.is_link_local,
        "exploded": net.network_address.exploded,
        "compressed": net.network_address.compressed,
        "hostmask": str(net.hostmask),
    }


def list_subnets(network_str: str, count: int = 20) -> dict:
    """列出后续 N 个相同前缀长度的子网。"""
    try:
        net = ipaddress.IPv4Network(network_str, strict=False)
    except (ValueError, ipaddress.AddressValueError) as e:
        return {"error": f"无效的网段: {e}"}

    subnets = []
    current = net
    for _ in range(count):
        hosts = list(current.hosts())
        subnets.append({
            "index": len(subnets) + 1,
            "network": str(current.network_address),
            "cidr": str(current),
            "first": str(hosts[0]) if hosts else "N/A",
            "last": str(hosts[-1]) if hosts else "N/A",
            "broadcast": str(current.broadcast_address),
            "mask": str(current.netmask),
        })
        # 下一个同大小子网
        next_addr = int(current.broadcast_address) + 1
        try:
            current = ipaddress.IPv4Network(f"{ipaddress.IPv4Address(next_addr)}/{net.prefixlen}", strict=False)
        except (ValueError, ipaddress.AddressValueError):
            break

    return {
        "parent": str(net),
        "prefix_len": net.prefixlen,
        "count": len(subnets),
        "hosts_per_subnet": net.num_addresses - 2,
        "subnets": subnets,
    }


def list_subnets_v6(network_str: str, count: int = 20) -> dict:
    """列出后续 N 个相同前缀长度的 IPv6 子网。"""
    try:
        net = ipaddress.IPv6Network(network_str, strict=False)
    except (ValueError, ipaddress.AddressValueError) as e:
        return {"error": f"无效的 IPv6 网段: {e}"}

    subnets = []
    current = net
    for _ in range(count):
        first = ipaddress.IPv6Address(int(current.network_address) + 1) if current.num_addresses > 2 else current.network_address
        last = ipaddress.IPv6Address(int(current.network_address) + current.num_addresses - 2) if current.num_addresses > 2 else current.network_address
        subnets.append({
            "index": len(subnets) + 1,
            "network": str(current.network_address),
            "cidr": str(current),
            "first": str(first),
            "last": str(last),
        })
        next_addr = int(current.network_address) + current.num_addresses
        try:
            current = ipaddress.IPv6Network(f"{ipaddress.IPv6Address(next_addr)}/{net.prefixlen}", strict=False)
        except (ValueError, ipaddress.AddressValueError):
            break

    return {
        "parent": str(net),
        "prefix_len": net.prefixlen,
        "count": len(subnets),
        "subnets": subnets,
    }


@router.get("")
def subnet_page(request: Request):
    return templates.TemplateResponse(request, "subnet.html", {})


@router.post("")
def calculate_subnet(
    request: Request,
    ipv4_addr: str = Form(default=""),
    ipv6_addr: str = Form(default=""),
    subnet_action: str = Form(default="calc"),
    new_prefix: str = Form(default=""),
    list_count: str = Form(default="20"),
):
    """统一处理 IPv4/IPv6 子网计算和划分。"""
    result = {}

    # IPv4 计算
    if ipv4_addr.strip():
        if subnet_action == "split" and new_prefix.strip():
            try:
                result["ipv4_split"] = calc_subnets(ipv4_addr.strip(), int(new_prefix))
            except ValueError:
                result["ipv4_split"] = {"error": "前缀长度必须是整数"}
        elif subnet_action == "list":
            cnt = int(list_count) if list_count.strip() else 20
            result["ipv4_list"] = list_subnets(ipv4_addr.strip(), max(1, min(cnt, 200)))
        else:
            result["ipv4"] = calc_ipv4(ipv4_addr.strip())
        result["ipv4_input"] = ipv4_addr.strip()

    # IPv6 计算
    if ipv6_addr.strip():
        if subnet_action == "list":
            cnt = int(list_count) if list_count.strip() else 20
            result["ipv6_list"] = list_subnets_v6(ipv6_addr.strip(), max(1, min(cnt, 200)))
        elif subnet_action == "split":
            result["ipv6_split"] = {"error": "IPv6 暂不支持子网划分，请使用列出后续子网功能"}
        else:
            result["ipv6"] = calc_ipv6(ipv6_addr.strip())
        result["ipv6_input"] = ipv6_addr.strip()

    if not result:
        result["error"] = "请输入 IPv4 或 IPv6 地址"

    return templates.TemplateResponse(request, "subnet.html", {**result})
