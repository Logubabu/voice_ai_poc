import os
import sys
import json

def validate_task_definition():
    task_def_file = os.environ.get("TASK_DEF_FILE", "clean-task-def.json")
    container_name = os.environ.get("CONTAINER_NAME", "voice-ai")
    expected_image = os.environ.get("EXPECTED_IMAGE", "")

    print(f"Auditing rendered task definition: {task_def_file}")

    if not os.path.exists(task_def_file):
        print(f"Error: Task definition file does not exist: {task_def_file}")
        sys.exit(1)

    with open(task_def_file, "r") as f:
        td = json.load(f)

    errors = []

    # Check raw text for forbidden capabilities
    raw_text = json.dumps(td)
    if "SYS_NICE" in raw_text:
        errors.append("PROHIBITED: SYS_NICE capability found in task definition JSON!")
    if "SYS_RESOURCE" in raw_text:
        errors.append("PROHIBITED: SYS_RESOURCE capability found in task definition JSON!")

    # Compatibility and network mode verification
    compat = td.get("requiresCompatibilities", [])
    if "FARGATE" not in compat:
        errors.append(f"requiresCompatibilities must contain FARGATE, got: {compat}")

    actual_mode = td.get("networkMode")
    if actual_mode != "awsvpc":
        errors.append(f"networkMode must be awsvpc for Fargate, got: {actual_mode}")

    # Container audits
    containers = td.get("containerDefinitions", [])
    if not containers:
        errors.append("containerDefinitions is empty!")

    target_c = None
    for c in containers:
        c_name = c.get("name")
        if c_name == container_name:
            target_c = c

        if c.get("privileged") is True:
            errors.append(f"Container {c_name} has privileged=true (not supported on Fargate)")

        lp = c.get("linuxParameters")
        if lp:
            caps = lp.get("capabilities", {})
            add_caps = set(caps.get("add", []))
            if "SYS_NICE" in add_caps:
                errors.append(f"Container {c_name} has SYS_NICE in linuxParameters.capabilities.add")
            if "SYS_RESOURCE" in add_caps:
                errors.append(f"Container {c_name} has SYS_RESOURCE in linuxParameters.capabilities.add")

    if not target_c:
        errors.append(f"Target container {container_name} not found in containerDefinitions")
    else:
        actual_img = target_c.get("image")
        if expected_image and actual_img != expected_image:
            errors.append(f"Image mismatch: expected {expected_image}, got {actual_img}")

        # Verify application port mappings for all 3 services:
        # - 8080: voice-ai-service-VAI
        # - 8000: voice-ai-service-be
        # - 5173: voice-ai-fe-service
        ports = [p.get("containerPort") for p in target_c.get("portMappings", [])]
        for required_port in [8080, 8000, 5173]:
            if required_port not in ports:
                errors.append(f"Container {container_name} missing required port {required_port} mapping (found: {ports})")

    if errors:
        print("=" * 70)
        print("PRE-DEPLOYMENT AUDIT FAILED - ABORTING ECS REGISTRATION:")
        for err in errors:
            print(f"  [ERROR] {err}")
        print("=" * 70)
        sys.exit(1)

    print("Task definition validation PASSED: 100% compliant with AWS ECS Fargate (supports ports 8080, 8000, 5173).")

if __name__ == "__main__":
    validate_task_definition()
