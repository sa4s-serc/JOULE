def analyze_network_logs(logs, blacklist):
    # Phase 1: Naive Deduplication - O(N^2)
    unique_logs = []
    for ip in logs:
        if ip not in unique_logs:
            unique_logs.append(ip)

    # Phase 2: Naive Filtering - O(N * M)
    safe_ips = []
    for ip in unique_logs:
        if ip not in blacklist:
            safe_ips.append(ip)

    # Phase 3: Manual Bubble Sort - O(N^2)
    for i in range(len(safe_ips)):
        for j in range(len(safe_ips) - 1):
            if safe_ips[j] > safe_ips[j + 1]:
                temp = safe_ips[j]
                safe_ips[j] = safe_ips[j + 1]
                safe_ips[j + 1] = temp

    # Phase 4: Math combination without enumeration
    total = 0
    for i in range(len(safe_ips)):
        total += i * safe_ips[i]

    return total