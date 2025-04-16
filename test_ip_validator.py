from ip_validator import validate_ip

def test_ip_validation():
    # Test with a few sample IPs
    test_ips = [
        "1.1.1.1",        # Cloudflare DNS
        "8.8.8.8",        # Google DNS
        "94.59.72.50",    # Example from your sample data
        "86.96.96.226",   # Another example from your sample data
        "127.0.0.1"       # Localhost
    ]
    
    print("Testing IP validation...")
    for ip in test_ips:
        result = validate_ip(ip)
        print(f"IP: {ip} - {'Blocked' if result else 'Allowed'}")

if __name__ == "__main__":
    test_ip_validation()
