import os
import importlib.util
import inspect
from .base_service import BaseService
    
class ServiceOrchestrator():

    def __init__(self):
        self._services = []

    def register_service_sample(self, client=None):
        """Register a new service object."""
        # Path to services folder (relative to current working directory)
        services_folder = os.path.join(os.getcwd(), 'services')

        # Check if services folder exists
        if not os.path.exists(services_folder):
            print(f"Services folder not found: {services_folder}")
            print(f"Current working directory: {os.getcwd()}")
            print("Make sure you have a 'services' directory with your service files.")
            return

        # Get all Python files in services folder
        python_files = [f for f in os.listdir(services_folder)
                   if f.endswith('.py') and f != '__init__.py']

        for file_name in python_files:
            try:
                # Construct full file path
                file_path = os.path.join(services_folder, file_name)

                # Create module name from filename (without .py extension)
                module_name = file_name[:-3]

                # Load module dynamically
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Skip imported classes (only get classes defined in this module)
                    # AND check if the class inherits from BaseService
                    if (obj.__module__ == module_name and 
                        issubclass(obj, BaseService) and 
                        obj is not BaseService):
                        try:
                            # Create instance of the class
                            service_instance = obj(client)

                            # Add to services list if not already present
                            if service_instance not in self._services:
                                self._services.append(service_instance)
                                print(f"Registered service: {name} from {file_name}")
                            else:
                                print(f"Service {name} already registered")

                        except Exception as e:
                            print(f"Failed to instantiate {name} from {file_name}: {e}")

            except Exception as e:
                print(f"Failed to load module {file_name}: {e}")

        print(f"Total services registered: {len(self._services)}")

    def register_service(self, client=None):
        """Register service test objects from perf_*_test.py files in current directory."""
        # Use current working directory instead of services folder
        current_folder = os.getcwd()

        # Get all Python files matching perf_*_test.py pattern in current directory
        test_files = [f for f in os.listdir(current_folder)
                     if f.startswith('perf_') and f.endswith('_test.py')]

        if not test_files:
            print(f"No perf_*_test.py files found in {current_folder}")
            return

        for file_name in test_files:
            try:
                # Construct full file path
                file_path = os.path.join(current_folder, file_name)

                # Create module name from filename (without .py extension)
                module_name = file_name[:-3]

                # Load module dynamically
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Skip imported classes (only get classes defined in this module)
                    # AND check if the class inherits from BaseService
                    if (obj.__module__ == module_name and 
                        issubclass(obj, BaseService) and 
                        obj is not BaseService):
                        try:
                            # Create instance of the class
                            service_instance = obj(client)

                            # Add to services list if not already present
                            if service_instance not in self._services:
                                self._services.append(service_instance)
                                print(f"Registered service test: {name} from {file_name}")
                            else:
                                print(f"Service test {name} already registered")

                        except Exception as e:
                            print(f"Failed to instantiate {name} from {file_name}: {e}")

            except Exception as e:
                print(f"Failed to load test module {file_name}: {e}")

        print(f"Total service tests registered: {len(self._services)}")

    def get_services(self):
        """Return a list of all registered services."""
        return self._services

    def unregister_service(self, service):
        """Unregister an existing service object."""
        if service in self._services:
            self._services.remove(service)

    def find_service(self, name):
        """Find a service by its name attribute."""
        for service in self._services:
            if hasattr(service, 'name') and service.name == name:
                return service
        return None

if __name__ == "__main__":
    obj = ServiceOrchestrator()
    obj.register_service()
    print("Registered services are", obj.get_services)
