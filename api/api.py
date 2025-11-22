# @TODO: API for the Scarface Strategy

# Let's create a flask app
from flask import Flask, jsonify, request
from flask_cors import CORS
import yaml
import os
import csv
import json
import time
from pathlib import Path

# Get the config file path relative to this file's location
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

app = Flask(__name__)
# Enable CORS for all routes
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==================== CACHING UTILITIES ====================

# Cache storage
_file_content_cache = {}
_directory_listing_cache = {}
_cache_metadata = {}  # Store mtime, size, and timestamp

# Cache configuration (will be set after config is loaded)
CACHE_TTL = 10  # Default, will be updated from config
MAX_CACHE_SIZE = 200  # Max number of files to cache

# Update CACHE_TTL from config
CACHE_TTL = int(config.get('cache_timer', 10))

def get_file_mtime_size(file_path):
    """Get file modification time and size."""
    try:
        stat = os.stat(file_path)
        return stat.st_mtime, stat.st_size
    except OSError:
        return None, None

def get_directory_mtime(dir_path):
    """Get directory modification time (approximate - uses most recent file mtime)."""
    try:
        max_mtime = 0
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            try:
                mtime = os.path.getmtime(item_path)
                max_mtime = max(max_mtime, mtime)
            except OSError:
                continue
        return max_mtime
    except OSError:
        return 0

def get_cached_directory_listing(path):
    """Get directory listing with caching."""
    cache_key = f"dir:{path}"
    now = time.time()
    
    # Check cache
    if cache_key in _directory_listing_cache:
        cached_info = _cache_metadata.get(cache_key)
        if cached_info:
            cached_data, cached_time, cached_mtime = cached_info
            if cached_data and (now - cached_time) < CACHE_TTL:
                current_mtime = get_directory_mtime(path)
                if current_mtime == cached_mtime:
                    return cached_data
    
    # Read directory
    items = []
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isdir(item_path):
            items.append(item)
    result = sorted(items)
    
    # Cache it
    current_mtime = get_directory_mtime(path)
    _directory_listing_cache[cache_key] = result
    _cache_metadata[cache_key] = (result, now, current_mtime)
    
    # Simple LRU: remove oldest if cache too large
    if len(_directory_listing_cache) > MAX_CACHE_SIZE:
        dir_keys = [k for k in _cache_metadata.keys() if k.startswith('dir:')]
        if dir_keys:
            oldest_key = min(dir_keys, 
                           key=lambda k: _cache_metadata[k][1] if len(_cache_metadata[k]) > 1 else 0)
            if oldest_key in _directory_listing_cache:
                del _directory_listing_cache[oldest_key]
            if oldest_key in _cache_metadata:
                del _cache_metadata[oldest_key]
    
    return result

def get_cached_file_listing(path, filter_txt_csv=True):
    """
    Get file listing with caching.
    
    Args:
        path: Directory path
        filter_txt_csv: If True, filter out files ending with -txt.csv
    """
    cache_key = f"files:{path}:{filter_txt_csv}"
    now = time.time()
    
    # Check cache
    if cache_key in _directory_listing_cache:
        cached_info = _cache_metadata.get(cache_key)
        if cached_info:
            cached_data, cached_time, cached_mtime = cached_info
            if cached_data and (now - cached_time) < CACHE_TTL:
                current_mtime = get_directory_mtime(path)
                if current_mtime == cached_mtime:
                    return cached_data
    
    # Read files
    files_list = []
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        if os.path.isfile(item_path):
            if not filter_txt_csv or not item.endswith('-txt.csv'):
                files_list.append(item)
    result = sorted(files_list)
    
    # Cache it
    current_mtime = get_directory_mtime(path)
    _directory_listing_cache[cache_key] = result
    _cache_metadata[cache_key] = (result, now, current_mtime)
    
    return result

def get_cached_file_content(file_path, content_type='auto'):
    """
    Get file content with caching based on modification time.
    
    Args:
        file_path: Path to file
        content_type: 'json', 'csv', 'raw', or 'auto'
    """
    cache_key = f"file:{file_path}"
    mtime, size = get_file_mtime_size(file_path)
    
    if mtime is None:
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check cache
    if cache_key in _file_content_cache:
        cached_info = _cache_metadata.get(cache_key)
        if cached_info:
            cached_mtime, cached_size, cached_data = cached_info
            if cached_data and cached_mtime == mtime and cached_size == size:
                return cached_data
    
    # Read and process file
    if content_type == 'auto':
        if file_path.endswith('.json'):
            content_type = 'json'
        elif file_path.endswith('.csv'):
            content_type = 'csv'
        else:
            content_type = 'raw'
    
    if content_type == 'json':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            result = {"data": data, "count": len(data)}
        elif isinstance(data, dict) and 'data' in data:
            result = data
        else:
            result = {"data": [data], "count": 1}
    elif content_type == 'csv':
        result = csv_to_json(file_path)
    else:  # raw
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            result = {"content": content}
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            result = {"content": content}
    
    # Cache it
    _file_content_cache[cache_key] = result
    _cache_metadata[cache_key] = (mtime, size, result)
    
    # Simple LRU: remove oldest if cache too large
    if len(_file_content_cache) > MAX_CACHE_SIZE:
        file_keys = [k for k in _cache_metadata.keys() if k.startswith('file:')]
        if file_keys:
            oldest_key = min(file_keys, 
                           key=lambda k: _cache_metadata[k][0] if len(_cache_metadata[k]) > 2 else 0)
            if oldest_key in _file_content_cache:
                del _file_content_cache[oldest_key]
            if oldest_key in _cache_metadata:
                del _cache_metadata[oldest_key]
    
    return result

def get_cached_log_lines(file_path):
    """Get log file lines with caching."""
    cache_key = f"log_lines:{file_path}"
    mtime, size = get_file_mtime_size(file_path)
    
    if mtime is None:
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Check cache
    if cache_key in _file_content_cache:
        cached_info = _cache_metadata.get(cache_key)
        if cached_info:
            cached_mtime, cached_size, cached_lines = cached_info
            if cached_lines and cached_mtime == mtime and cached_size == size:
                return cached_lines
    
    # Read lines
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            lines = f.readlines()
    
    # Cache it
    _file_content_cache[cache_key] = lines
    _cache_metadata[cache_key] = (mtime, size, lines)
    
    return lines


def is_json_content(content):
    """
    Check if content is already in JSON format.
    
    Args:
        content: String content to check
        
    Returns:
        bool: True if content is valid JSON, False otherwise
    """
    try:
        json.loads(content)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def csv_to_json(csv_file_path):
    """
    Utility function to convert CSV file to JSON format.
    First checks if the file is already in JSON format.
    
    Args:
        csv_file_path: Path to the CSV file
        
    Returns:
        dict: Dictionary with 'data' key containing list of row dictionaries,
              and 'count' key with the number of rows
    """
    # First, try to read and check if it's already JSON
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if is_json_content(content):
                # File is already JSON, parse it
                json_data = json.loads(content)
                # If it's already in our expected format, return it
                if isinstance(json_data, dict) and 'data' in json_data:
                    return json_data
                # If it's a list, wrap it in our format
                if isinstance(json_data, list):
                    return {
                        "data": json_data,
                        "count": len(json_data)
                    }
                # If it's a dict but not in our format, wrap it
                return {
                    "data": [json_data] if isinstance(json_data, dict) else json_data,
                    "count": 1 if isinstance(json_data, dict) else len(json_data) if isinstance(json_data, list) else 0
                }
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        try:
            with open(csv_file_path, 'r', encoding='latin-1') as f:
                content = f.read().strip()
                if is_json_content(content):
                    json_data = json.loads(content)
                    if isinstance(json_data, dict) and 'data' in json_data:
                        return json_data
                    if isinstance(json_data, list):
                        return {
                            "data": json_data,
                            "count": len(json_data)
                        }
                    return {
                        "data": [json_data] if isinstance(json_data, dict) else json_data,
                        "count": 1 if isinstance(json_data, dict) else len(json_data) if isinstance(json_data, list) else 0
                    }
        except Exception:
            pass  # Fall through to CSV parsing
    
    # If not JSON, parse as CSV
    data = []
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                data.append(row)
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        with open(csv_file_path, 'r', encoding='latin-1') as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                data.append(row)
    
    return {
        "data": data,
        "count": len(data)
    }

@app.route(f"/api/{config['app']['api_version']}/health", methods=["GET"], strict_slashes=False)
def health():
    return jsonify({"status": "ok"})


# Get all directories under the portfolios folder
@app.route(f"/api/{config['app']['api_version']}/directories", methods=["GET"], strict_slashes=False)
def directories():    
    portfolios_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder']))
    
    # Check if the path exists
    if not os.path.exists(portfolios_abs_path):
        return jsonify({"error": f"Portfolios folder not found: {portfolios_abs_path}"}), 404
    
    try:
        directories_list = get_cached_directory_listing(portfolios_abs_path)
    except PermissionError:
        return jsonify({"error": f"Permission denied accessing: {portfolios_abs_path}"}), 403
    except FileNotFoundError:
        return jsonify({"error": f"Portfolios folder not found: {portfolios_abs_path}"}), 404
    except Exception as e:
        return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
    
    # Return directories in JSON format
    return jsonify({
        "path": portfolios_abs_path,
        "directories": directories_list
    })
    
    
# Get portfolios look for results directory and return all the directories under it
@app.route(f"/api/{config['app']['api_version']}/portfolios", methods=["GET"], strict_slashes=False)
def portfolios():
    portfolios_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], 'results'))
    
    if not os.path.exists(portfolios_abs_path):
        return jsonify({"error": f"Portfolios folder not found: {portfolios_abs_path}"}), 404
    
    try:
        portfolios_list = get_cached_directory_listing(portfolios_abs_path)
    except Exception as e:
        return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
    
    return jsonify({
        "path": portfolios_abs_path,
        "portfolios": portfolios_list
    })
    
# get all files under a directory and portfolio id
@app.route(f"/api/{config['app']['api_version']}/files/<directory>/<portfolio_id>", methods=["GET"], strict_slashes=False)
def files(directory, portfolio_id):
    files_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], directory, portfolio_id))
    
    # Check if the path exists
    if not os.path.exists(files_abs_path):
        return jsonify({"error": f"Directory not found: {files_abs_path}"}), 404
    
    # Check if it's actually a directory
    if not os.path.isdir(files_abs_path):
        return jsonify({"error": f"Path is not a directory: {files_abs_path}"}), 400
    
    try:
        files_list = get_cached_file_listing(files_abs_path)
    except PermissionError:
        return jsonify({"error": f"Permission denied accessing: {files_abs_path}"}), 403
    except Exception as e:
        return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
    
    return jsonify({
        "path": files_abs_path,
        "files": files_list
    })


# get file content in json format
@app.route(f"/api/{config['app']['api_version']}/files/<directory>/<portfolio_id>/<file>", methods=["GET"], strict_slashes=False)
def file_content(directory, portfolio_id, file):
    file_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], directory, portfolio_id, file))
    
    if not os.path.exists(file_abs_path):
        return jsonify({"error": f"File not found: {file_abs_path}"}), 404
    
    try:
        if file.endswith('.json'):
            result = get_cached_file_content(file_abs_path, 'json')
        elif file.endswith('.csv'):
            result = get_cached_file_content(file_abs_path, 'csv')
        else:
            result = get_cached_file_content(file_abs_path, 'raw')
        
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"error": f"File not found: {file_abs_path}"}), 404
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid JSON file: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Error reading file: {str(e)}"}), 500


# ==================== LOGS ROUTES ====================

# Get all directories under logs folder for a portfolio
@app.route(f"/api/{config['app']['api_version']}/logs/directories/<portfolio_id>", methods=["GET"], strict_slashes=False)
def log_directories(portfolio_id):
    """
    Get all directories under logs folder for a specific portfolio.
    Returns directories that will be used as dropdown options.
    """
    logs_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], 'logs', portfolio_id))
    
    # Check if the path exists
    if not os.path.exists(logs_abs_path):
        return jsonify({"error": f"Logs folder not found: {logs_abs_path}"}), 404
    
    # Check if it's actually a directory
    if not os.path.isdir(logs_abs_path):
        return jsonify({"error": f"Path is not a directory: {logs_abs_path}"}), 400
    
    try:
        directories_list = get_cached_directory_listing(logs_abs_path)
    except PermissionError:
        return jsonify({"error": f"Permission denied accessing: {logs_abs_path}"}), 403
    except Exception as e:
        return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
    
    return jsonify({
        "path": logs_abs_path,
        "directories": directories_list
    })


# Get all files in a specific log directory
@app.route(f"/api/{config['app']['api_version']}/logs/files/<portfolio_id>/<log_directory>", methods=["GET"], strict_slashes=False)
def log_files(portfolio_id, log_directory):
    """
    Get all files in a specific log directory for a portfolio.
    Returns list of log files that can be viewed.
    """
    log_dir_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], 'logs', portfolio_id, log_directory))
    
    # Check if the path exists
    if not os.path.exists(log_dir_abs_path):
        return jsonify({"error": f"Log directory not found: {log_dir_abs_path}"}), 404
    
    # Check if it's actually a directory
    if not os.path.isdir(log_dir_abs_path):
        return jsonify({"error": f"Path is not a directory: {log_dir_abs_path}"}), 400
    
    try:
        files_list = get_cached_file_listing(log_dir_abs_path, filter_txt_csv=False)
    except PermissionError:
        return jsonify({"error": f"Permission denied accessing: {log_dir_abs_path}"}), 403
    except Exception as e:
        return jsonify({"error": f"Error reading directory: {str(e)}"}), 500
    
    return jsonify({
        "path": log_dir_abs_path,
        "files": files_list
    })


# Get log file content with pagination
@app.route(f"/api/{config['app']['api_version']}/logs/content/<portfolio_id>/<log_directory>/<file>", methods=["GET"], strict_slashes=False)
def log_content(portfolio_id, log_directory, file):
    """
    Get log file content with pagination support.
    Query parameters:
    - page: Page number (default: 1)
    - per_page: Number of lines per page (default: 1000)
    - search: Optional search query to filter lines
    """
    file_abs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), config['data_folder'], 'logs', portfolio_id, log_directory, file))
    
    if not os.path.exists(file_abs_path):
        return jsonify({"error": f"Log file not found: {file_abs_path}"}), 404
    
    if not os.path.isfile(file_abs_path):
        return jsonify({"error": f"Path is not a file: {file_abs_path}"}), 400
    
    # Get pagination parameters
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=1000, type=int)
    search_query = request.args.get('search', default='', type=str)
    
    # Validate parameters
    if page < 1:
        return jsonify({"error": "Page must be >= 1"}), 400
    if per_page < 1 or per_page > 10000:
        return jsonify({"error": "per_page must be between 1 and 10000"}), 400
    
    try:
        # Use cached lines
        lines = get_cached_log_lines(file_abs_path)
    except FileNotFoundError:
        return jsonify({"error": f"Log file not found: {file_abs_path}"}), 404
    except Exception as e:
        return jsonify({"error": f"Error reading log file: {str(e)}"}), 500
    
    total_lines = len(lines)
    
    # Filter by search query if provided
    if search_query:
        filtered_lines = [
            (i+1, line) for i, line in enumerate(lines) 
            if search_query.lower() in line.lower()
        ]
        total_filtered = len(filtered_lines)
        
        # Paginate filtered results
        start = (page - 1) * per_page
        end = start + per_page
        paginated = filtered_lines[start:end]
        
        return jsonify({
            "type": "log",
            "lines": [{"lineNumber": num, "content": content.rstrip('\n\r')} for num, content in paginated],
            "totalLines": total_filtered,
            "originalTotalLines": total_lines,
            "page": page,
            "perPage": per_page,
            "totalPages": (total_filtered + per_page - 1) // per_page if total_filtered > 0 else 1,
            "hasSearch": True,
            "searchQuery": search_query
        })
    else:
        # Paginate all lines
        start = (page - 1) * per_page
        end = start + per_page
        paginated = [(i+1, lines[i]) for i in range(start, min(end, total_lines))]
        
        return jsonify({
            "type": "log",
            "lines": [{"lineNumber": num, "content": content.rstrip('\n\r')} for num, content in paginated],
            "totalLines": total_lines,
            "originalTotalLines": total_lines,
            "page": page,
            "perPage": per_page,
            "totalPages": (total_lines + per_page - 1) // per_page if total_lines > 0 else 1,
            "hasSearch": False
        })

if __name__ == "__main__":
    app.run(debug=True)
