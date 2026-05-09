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
    
    # 0. Initialize TPM (required after swtpm starts)
    print("[*] Initializing TPM...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_startup", "-c"], check=False, capture_output=True)

    # 1. Start fresh by clearing the TPM (Owner hierarchy)
    print("[*] Clearing TPM state...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_clear", "-c", "o"], check=False, capture_output=True)
    
    # 2. Aggressively flush all context types (transient, loaded, session)
    print("[*] Flushing all contexts...")
    for ctype in ["-t", "-l", "-s"]:
        subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", ctype], check=False, capture_output=True)
    
    # 3. Create primary handle in the Endorsement hierarchy
    print("[*] Creating primary handle...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_createprimary", "-C", "e", "-g", "sha256", "-G", "rsa", "-c", "primary.ctx"], check=True)
    
    # 4. Create restricted signing key (AIK)
    print("[*] Creating AIK...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_create", "-C", "primary.ctx", "-g", "sha256", "-G", "rsa2048:rsassa-sha256:null", "-u", "aik.pub", "-r", "aik.priv"], check=True)
    
    # 5. Flush BEFORE loading to maximize available memory
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_flushcontext", "-t"], check=False, capture_output=True)

    # 6. Load AIK into TPM
    print("[*] Loading AIK into TPM...")
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_load", "-C", "primary.ctx", "-u", "aik.pub", "-r", "aik.priv", "-c", "aik.ctx"], check=True)
    
    # 7. Persist to a fixed handle
    print("[*] Persisting AIK to 0x81000002...")
    # If 0x81000002 is occupied, evict it first
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_evictcontrol", "-C", "o", "-c", "0x81000002"], check=False, capture_output=True)
    subprocess.run(["docker", "exec"] + env + ["sovereign-app", "tpm2_evictcontrol", "-C", "o", "-c", "aik.ctx", "0x81000002"], check=True)
    
    # 8. Final cleanup
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
