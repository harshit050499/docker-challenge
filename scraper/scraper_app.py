from flask import Flask, jsonify
import http.client
import json
import socket

app = Flask(__name__)

def get_unix_socket_connection():
    """Create a Unix socket connection."""
    return http.client.HTTPConnection("localhost", 80, timeout=10)

def list_running_containers():
    """List all running containers."""
    try:
        conn = get_unix_socket_connection()
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect('/var/run/docker.sock')
        conn.request("GET", "/containers/json")
        response = conn.getresponse()
        containers = json.loads(response.read().decode())
        return [container["Id"] for container in containers]
    except Exception as e:
        return {"error": str(e)}

def get_container_stats(container_id):
    """Fetch metrics for a given container."""
    try:
        conn = get_unix_socket_connection()
        conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock.connect('/var/run/docker.sock')
        conn.request("GET", f"/containers/{container_id}/stats?stream=false")
        response = conn.getresponse()
        if response.status != 200:
            return {"error": f"Failed to get stats - {response.read().decode()}"}

        stats = json.loads(response.read().decode())
        return {
            "container_id": container_id,
            "cpu_usage": calculate_cpu_percent(stats),
            "memory_usage": stats["memory_stats"]["usage"],
            "memory_limit": stats["memory_stats"]["limit"],
            "network_io": stats["networks"],
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_cpu_percent(stats):
    """Calculate CPU usage percentage."""
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                    stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                       stats["precpu_stats"]["system_cpu_usage"]

        # Check for presence of 'percpu_usage'
        percpu_usage = stats["cpu_stats"].get("cpu_usage", {}).get("percpu_usage", [])
        
        if system_delta > 0 and cpu_delta > 0:
            # Use the length of percpu_usage or default to 1
            cpu_count = len(percpu_usage) if percpu_usage else 1
            return (cpu_delta / system_delta) * cpu_count * 100.0
        
        return 0.0
    except KeyError as e:
        return {"error": f"Key error: {str(e)}"}  # Handle missing keys gracefully

@app.route('/metrics', methods=['GET'])
def metrics():
    """Endpoint to return metrics for all containers."""
    container_ids = list_running_containers()
    all_metrics = [get_container_stats(container_id) for container_id in container_ids]
    return jsonify(all_metrics)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9100)
