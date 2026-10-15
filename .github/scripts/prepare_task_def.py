import os
import sys
import json

def prepare_task_definition():
    base_file = os.environ.get("BASE_DEF", "task-definition.json")
    if not os.path.exists(base_file):
        print(f"Error: Base task definition file not found: {base_file}")
        sys.exit(1)

    print(f"Reading base task definition from: {base_file}")
    with open(base_file, "r") as f:
        td = json.load(f)

    # 1. Strip AWS-managed read-only metadata fields rejected by RegisterTaskDefinition
    readonly_fields = [
        "taskDefinitionArn", "revision", "status", "requiresAttributes",
        "compatibilities", "registeredAt", "registeredBy"
    ]
    for field in readonly_fields:
        td.pop(field, None)

    # 2. Strict AWS Fargate configuration
    td["requiresCompatibilities"] = ["FARGATE"]
    td["networkMode"] = "awsvpc"

    if "runtimePlatform" not in td:
        td["runtimePlatform"] = {
            "cpuArchitecture": "X86_64",
            "operatingSystemFamily": "LINUX"
        }

    # 3. Purge SYS_NICE, SYS_RESOURCE, and unsupported Linux capabilities
    forbidden_caps = {"SYS_NICE", "SYS_RESOURCE", "SYS_ADMIN", "NET_ADMIN", "ALL"}
    for c in td.get("containerDefinitions", []):
        if "privileged" in c:
            c["privileged"] = False

        lp = c.get("linuxParameters")
        if lp:
            caps = lp.get("capabilities")
            if caps:
                if "add" in caps:
                    caps["add"] = [cap for cap in caps["add"] if cap not in forbidden_caps]
                    if not caps["add"]:
                        caps.pop("add", None)
                if "drop" in caps and not caps["drop"]:
                    caps.pop("drop", None)
                if not caps:
                    lp.pop("capabilities", None)
            if not lp:
                c.pop("linuxParameters", None)

        # 4. Inject runtime environment configuration and secrets
        env_list = c.setdefault("environment", [])
        existing = {item.get("name"): item for item in env_list}

        # Default working configurations
        defaults = {
            "PYTHONUNBUFFERED": "1",
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "INFO",
            "STT_PROVIDER": "groq",
            "LLM_PROVIDER": "google",
            "LLM_MODEL": "gemini-3.5-flash",
            "TTS_PROVIDER": "elevenlabs",
            "ELEVENLABS_VOICE_ID": "JBFqnCBsd6RMkjVDRZzb",
            "ELEVENLABS_MODEL": "eleven_flash_v2_5",
            "CORS_ALLOW_ALL": "true",
            "FREESWITCH_ENABLED": "true",
            "FREESWITCH_HOST": "127.0.0.1:8021",
            "WEB_SEARCH_PROVIDER": "duckduckgo",
            "QDRANT_URL": "http://qdrant:6333",
            "AUTO_DISCOVER_PUBLIC_IP": "true",
        }
        for k, v in defaults.items():
            if k in existing:
                existing[k]["value"] = v
            else:
                env_list.append({"name": k, "value": v})

        # Inject bulk ENV_FILE secret if provided in GitHub Secrets
        raw_env_file = os.environ.get("ENV_FILE", "").strip()
        if raw_env_file:
            parsed_count = 0
            for line in raw_env_file.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v:
                        if k in existing:
                            existing[k]["value"] = v
                        else:
                            env_list.append({"name": k, "value": v})
                        parsed_count += 1
            print(f"Injected {parsed_count} variables from GitHub secret ENV_FILE")

        # Inject individual secrets if available in GitHub workflow environment
        secret_names = [
            "GEMINI_API_KEY", "GROQ_API_KEY", "STT_API_KEY", "SARVAM_API_KEY",
            "ELEVENLABS_API_KEY", "TTS_API_KEY", "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"
        ]
        for sec in secret_names:
            val = os.environ.get(sec, "").strip()
            if val:
                if sec in existing:
                    existing[sec]["value"] = val
                else:
                    env_list.append({"name": sec, "value": val})

        # Diagnostic audit of injected keys without printing secret values
        configured_keys = {item.get("name") for item in env_list if item.get("value")}
        print(f"Container environment has {len(configured_keys)} configured keys.")
        for check_key in ["GROQ_API_KEY", "GEMINI_API_KEY", "ELEVENLABS_API_KEY", "TWILIO_ACCOUNT_SID"]:
            is_set = check_key in configured_keys
            print(f"  - {check_key}: {'CONFIGURED' if is_set else 'NOT CONFIGURED (Will fail if called)'}")

    output_file = "clean-task-def.json"
    with open(output_file, "w") as f:
        json.dump(td, f, indent=2)

    print(f"Successfully prepared clean Fargate task definition at {output_file}")

if __name__ == "__main__":
    prepare_task_definition()
