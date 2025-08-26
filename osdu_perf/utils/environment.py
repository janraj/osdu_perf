"""
Environment detection and configuration utilities.
"""

import os
from typing import Dict, Any


def detect_environment() -> str:
    """
    Detect the current environment (dev, staging, prod).
    
    Returns:
        str: Environment name
    """
    env = os.getenv('ENVIRONMENT', 'dev').lower()
    if env in ['dev', 'development']:
        return 'dev'
    elif env in ['staging', 'stage']:
        return 'staging'
    elif env in ['prod', 'production']:
        return 'prod'
    else:
        return 'dev'


def get_environment_config() -> Dict[str, Any]:
    """
    Get environment-specific configuration.
    
    Returns:
        Dict: Configuration settings
    """
    env = detect_environment()
    
    config = {
        'dev': {
            'use_managed_identity': False,
            'log_level': 'DEBUG',
            'timeout': 30,
        },
        'staging': {
            'use_managed_identity': True,
            'log_level': 'INFO',
            'timeout': 60,
        },
        'prod': {
            'use_managed_identity': True,
            'log_level': 'WARNING',
            'timeout': 120,
        }
    }
    
    return config.get(env, config['dev'])
