import ipaddress
import itertools
import math

MAX_LISTED_SUBNETS = 64


def subnet_info(cidr: str) -> dict:
    """Get the details of an IPv4 subnet written in CIDR notation, for example
    '192.168.1.0/26' or '10.0.5.77/20'. Returns the network address, subnet mask,
    broadcast address, first and last usable host address, and the number of
    usable hosts. Use this for any subnetting question."""
    try:
        net = ipaddress.IPv4Network(cidr, strict=False)
    except ValueError as e:
        return {"error": str(e)}
    total = net.num_addresses
    usable = max(total - 2, 0)  # classic rule: minus network and broadcast addresses
    result = {
        "network_address": str(net.network_address),
        "subnet_mask": str(net.netmask),
        "prefix_length": net.prefixlen,
        "broadcast_address": str(net.broadcast_address),
        "total_addresses": total,
        "usable_hosts": usable,
    }
    if usable > 0:
        result["first_usable_host"] = str(net.network_address + 1)
        result["last_usable_host"] = str(net.broadcast_address - 1)
    return result


def split_into_subnets(cidr: str, number_of_subnets: int) -> dict:
    """Split an IPv4 network into equal-sized subnets. The number of subnets must
    be a power of 2 (2, 4, 8, 16, ...). Example: cidr='192.168.1.0/24',
    number_of_subnets=4. Returns the list of subnets with their ranges (the first 64
    when there are more: 'truncated' then says so, and total_subnets gives the count)."""
    try:
        net = ipaddress.IPv4Network(cidr, strict=False)
    except ValueError as e:
        return {"error": str(e)}
    if number_of_subnets < 1 or (number_of_subnets & (number_of_subnets - 1)) != 0:
        return {"error": "number_of_subnets must be a power of 2 (2, 4, 8, ...)"}
    extra_bits = int(math.log2(number_of_subnets))
    new_prefix = net.prefixlen + extra_bits
    if new_prefix > 32:
        return {"error": "Not enough address bits to make that many subnets"}
    # islice: only the subnets that are shown are ever made (2^24 of them would not fit)
    subnets = [subnet_info(str(sub)) for sub in
               itertools.islice(net.subnets(new_prefix=new_prefix), MAX_LISTED_SUBNETS)]
    result = {"new_prefix_length": new_prefix, "total_subnets": number_of_subnets,
              "subnets": subnets, "truncated": number_of_subnets > MAX_LISTED_SUBNETS}
    if result["truncated"]:
        result["note"] = (f"Only the first {MAX_LISTED_SUBNETS} of {number_of_subnets} subnets are "
                          "listed. Each one holds the same number of addresses.")
    return result


def delay_calculation(packet_size_bits: float, link_rate_bps: float,
                      distance_m: float, propagation_speed_mps: float = 2e8) -> dict:
    """Calculate the delays for sending one packet over one link.
    packet_size_bits: packet length in BITS (1 byte = 8 bits).
    link_rate_bps: link speed in BITS PER SECOND (1 Mbps = 1,000,000).
    distance_m: link length in METERS.
    propagation_speed_mps: signal speed in meters/second (default 2e8, typical for cable).
    Returns transmission delay, propagation delay and their total, in milliseconds.
    Queuing and processing delays are not included."""
    if link_rate_bps <= 0 or propagation_speed_mps <= 0:
        return {"error": "link_rate_bps and propagation_speed_mps must be greater than 0."}
    transmission = packet_size_bits / link_rate_bps
    propagation = distance_m / propagation_speed_mps
    return {
        "transmission_delay_ms": transmission * 1000,
        "propagation_delay_ms": propagation * 1000,
        "total_delay_ms": (transmission + propagation) * 1000,
    }


def bandwidth_delay_product(link_rate_bps: float, propagation_delay_s: float) -> dict:
    """Calculate the bandwidth-delay product: the maximum number of bits that can
    be 'in flight' on a link. link_rate_bps is in bits per second and
    propagation_delay_s is the one-way propagation delay in SECONDS."""
    if link_rate_bps < 0 or propagation_delay_s < 0:
        return {"error": "link_rate_bps and propagation_delay_s cannot be negative."}
    bits = link_rate_bps * propagation_delay_s
    return {"bits_in_flight": bits, "bytes_in_flight": bits / 8}


# The list we give to the AI
ALL_TOOLS = [subnet_info, split_into_subnets, delay_calculation, bandwidth_delay_product]


# Quick self-test: run `python tools.py`
if __name__ == "__main__":
    print(subnet_info("192.168.1.77/26"))
    print(split_into_subnets("192.168.1.0/24", 4)["new_prefix_length"])
    print(delay_calculation(1000, 1_000_000, 1_000_000))
    print(bandwidth_delay_product(10_000_000, 0.05))