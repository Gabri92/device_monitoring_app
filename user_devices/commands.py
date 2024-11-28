import paramiko

def execute_ssh_command(ip, username, password, command):
    """
    Executes a command on a remote device via SSH.
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=username, password=password, timeout=10)

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        ssh.close()

        if error:
            return False, error
        return True, output
    except Exception as e:
        return False, str(e)

def set_pin_status(device, pin, status):
    """
    Sets the GPIO pin status on the Orange Pi via SSH.
    """
    # Command to set the GPIO pin
    gpio_status = "1" if status == "on" else "0"
    command = f"gpio write {pin} {gpio_status}"  # Example command; adjust for your device

    # Execute the command over SSH
    success, response = execute_ssh_command(
        ip=device.ssh_ip_address,
        username=device.ssh_username,
        password=device.ssh_password,
        command=command
    )

    return success, response
