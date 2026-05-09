import subprocess
import json
import base64
import os
import time

def extract_json(output):
    # Find the [Evidence Quote] section and parse the JSON block that follows
    lines = output.splitlines()
    in_json = False
    json_lines = []
    for line in lines:
        if "[Evidence Quote]" in line:
            in_json = True
            continue
        if in_json:
            json_lines.append(line)
            if line.strip() == "}":
                break
    return json.loads("\n".join(json_lines))

def provision_tpm():
    print("[*] Provisioning TPM simulator with AIK at 0x81000002...")
    env = ["-e", "TPM2TOOLS_TCTI=swtpm:host=tpm-simulator,port=2321"]
    
    # Initialize TPM (ignore error if already initialized)
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_startup", "-c"], check=False, capture_output=True)
    
    # Flush transient objects to avoid 0x902 (out of memory)
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-t"], check=False, capture_output=True)

    # Check if key exists
    res = subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_readpublic", "-c", "0x81000002"], capture_output=True)
    if res.returncode == 0:
        print("[+] AIK already provisioned.")
        return

    # Flush contexts to be safe
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-t"], check=False, capture_output=True)
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-s"], check=False, capture_output=True)
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-l"], check=False, capture_output=True)
    
    # Create primary
    print("[*] Creating primary handle...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_createprimary", "-C", "e", "-g", "sha256", "-G", "rsa", "-c", "primary.ctx"], check=True)
    
    # Flush transient again to make room for load
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-t"], check=False, capture_output=True)

    # Create restricted signing key
    print("[*] Creating AIK...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_create", "-C", "primary.ctx", "-g", "sha256", "-G", "rsa2048:rsassa-sha256:null", "-u", "aik.pub", "-r", "aik.priv"], check=True)
    
    # Load and persist
    print("[*] Loading AIK into TPM...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_load", "-C", "primary.ctx", "-u", "aik.pub", "-r", "aik.priv", "-c", "aik.ctx"], check=True)
    
    print("[*] Persisting AIK to 0x81000002...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_evictcontrol", "-C", "o", "-c", "aik.ctx", "0x81000002"], check=True)
    
    # Final cleanup of transient handles
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-t"], check=False, capture_output=True)
    print("[+] Provisioning complete.")

def main():
    provision_tpm()
    nonce = f"ci-test-{int(time.time())}"
    print(f"[*] Running attestation with nonce: {nonce}")
    
    cmd_attest = [
        "docker", "exec", 
        "sovereign-app", 
        "sh", "-c", f"PYTHONPATH=/app sovereign trust attest --nonce {nonce}"
    ]
    res_attest = subprocess.run(cmd_attest, capture_output=True, text=True)
    if res_attest.returncode != 0:
        print(f"[-] Attestation failed: {res_attest.stderr}")
        exit(1)
        
    try:
        quote_json = extract_json(res_attest.stdout)
    except Exception as e:
        print(f"[-] Failed to parse JSON output: {e}\nOutput was: {res_attest.stdout}")
        exit(1)
        
    if quote_json.get("type") != "TPM2_QUOTE":
        print(f"[-] Expected TPM2_QUOTE, got {quote_json.get('type')}. Simulation fallback active?")
        exit(1)

    print("[+] Successfully parsed TPM2_QUOTE evidence.")
    
    # Extract base64
    msg_bytes = base64.b64decode(quote_json["quote_data"])
    sig_bytes = base64.b64decode(quote_json["signature"])
    
    with open("quote.msg", "wb") as f:
        f.write(msg_bytes)
    with open("quote.sig", "wb") as f:
        f.write(sig_bytes)
        
    # Copy files into container for verification
    subprocess.run(["docker", "cp", "quote.msg", "sovereign-app:/tmp/quote.msg"], check=True)
    subprocess.run(["docker", "cp", "quote.sig", "sovereign-app:/tmp/quote.sig"], check=True)
    
    # Export public key
    print("[*] Extracting AIK public key from TPM...")
    cmd_pub = [
        "docker", "exec", "-e", "TPM2TOOLS_TCTI=swtpm:host=tpm-simulator,port=2321",
        "sovereign-app", 
        "tpm2_readpublic", "-c", "0x81000002", "-f", "pem", "-o", "/tmp/aik.pub"
    ]
    subprocess.run(cmd_pub, check=True)
    
    # Run tpm2_checkquote
    print("[*] Running cryptograhic verifier (tpm2_checkquote)...")
    # Using sha256 as hardcoded in the generator, checking against quote.msg and quote.sig
    cmd_verify = [
        "docker", "exec", "-e", "TPM2TOOLS_TCTI=swtpm:host=tpm-simulator,port=2321",
        "sovereign-app", 
        "tpm2_checkquote", 
        "-u", "/tmp/aik.pub", 
        "-m", "/tmp/quote.msg", 
        "-s", "/tmp/quote.sig",
        "-g", "sha256",
        "-q", nonce.encode().hex()
    ]
    
    res_verify = subprocess.run(cmd_verify, capture_output=True, text=True)
    if res_verify.returncode == 0:
        print("[+] SUCCESS! Quote is cryptographically valid and bound to the nonce.")
        exit(0)
    else:
        print(f"[-] VERIFICATION FAILED: {res_verify.stderr}")
        exit(1)

if __name__ == "__main__":
    main()
