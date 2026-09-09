"""Dynamic endpoints remain constrained by independently configured proxy-node networks."""
import ipaddress
from urllib.parse import urlsplit


def compile_endpoints(snapshot, networks, legacy_upstreams):
    admitted = set(legacy_upstreams)
    by_agent = {}
    for item in snapshot["endpoints"]:
        if set(item) != {"agentId", "instanceId", "nodeId", "host", "port", "scheme"}:
            raise ValueError("invalid endpoint envelope")
        if not all(isinstance(item[key], str) and item[key] for key in ("agentId", "instanceId", "nodeId", "host")):
            raise ValueError("endpoint identity missing")
        address = ipaddress.IPv4Address(item["host"])
        if (address.is_unspecified or address.is_multicast or address.is_link_local or address.is_reserved
                or str(address) == "100.100.100.200" or not any(address in network for network in networks)):
            raise ValueError("endpoint outside independently approved network")
        if address.is_loopback and not any(network.network_address.is_loopback for network in networks):
            raise ValueError("loopback requires explicit proxy-local network approval")
        if type(item["port"]) is not int or not 1 <= item["port"] <= 65535 or item["scheme"] not in {"http", "https"}:
            raise ValueError("invalid endpoint protocol or port")
        if item["agentId"] in by_agent:
            raise ValueError("multiple endpoints for one agent")
        origin = f'{item["scheme"]}://{item["host"]}:{item["port"]}'
        by_agent[item["agentId"]] = origin
        admitted.add((item["host"], item["port"]))
    used = set()
    seen = set()
    for route in snapshot["agents"]:
        agent = route["agentId"]
        if agent in seen:
            raise ValueError("duplicate agent route")
        seen.add(agent)
        upstream = route["upstreamRef"].rstrip("/")
        if agent in by_agent:
            if upstream != by_agent[agent] or route["status"] != "PUBLISHED" or route["identityMode"] != "SIGNED_TOKEN":
                raise ValueError("route does not match its admitted endpoint")
            used.add(agent)
        else:
            target = urlsplit(upstream)
            if (target.hostname, target.port or (443 if target.scheme == "https" else 80)) not in legacy_upstreams:
                raise ValueError("agent has no independently admitted endpoint")
    if used != set(by_agent):
        raise ValueError("unreferenced dynamic endpoint")
    return frozenset(admitted)
