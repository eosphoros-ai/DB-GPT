from pilot.configs.config import Config
from pilot.connections.manages.connection_manager import ConnectManager

if __name__ == "__main__":
    mange= ConnectManager()
    types = mange.get_all_completed_types()
    print(str(types))