import requests
print('# ###########################')


host= '127.0.0.1'
host= 'localhost'
port = 5107

    # d = {
    #   "request_type": "BUY_ORDER",
    #   "base_strike": 6810,
    #   "user_price": 1,
    #   "expiry": "20251217",
    #   "web_request_id": "saeed-1",
    #   "web_timestamp": "2025-12-11 16:44:18",
    #   "status": "WEB_SENT"
    # }
    # d = {
    #     "order_set_id": "SET-20251216-154252-85",  # TODO u need to change it every time
    #     "base_strike": 6810,
    #     "expiry": 20251216,
    #     "user_price" : -20,
    #     "web_request_id": "100",
    #     "request_type": "CLOSE_ORDER_SET",
    #     "memo": "A request from Web to close order ",
    #     'status': 'PY_SENT'
    # }

def get_close_all_positions():
    d = {
        "web_request_id": "100",
        "request_type": "CLOSE_ALL_POSITIONS",
        "memo": "A request from API sandbox ",
        'status': 'PY_SENT'
    }

    return d , "api/send_request"

def get_closed_order_sets():
    d = {
        "web_request_id": "100",
        "request_type": "GET_CLOSED_ORDER_SETS",
        "memo": "A request from API sandbox ",
        'status': 'PY_SENT'
    }

    return d , "api/get-closed-order-sets" , "get"


def cancel_all_open_orders():
    d = {
        "web_request_id": "101",
        "request_type": "CANCEL_ALL_ORDERS",
        "memo": "A request from API sandbox ",
        'status': 'PY_SENT'
    }

    return d, "api/send-request"


def view_file():
    d = {
        "web_request_id": "101",
        "request_type": "VIEW_FILE",
        "file_name": "config-manual-settings.yaml",
        "memo": "A request from API sandbox ",
        'status': 'PY_SENT'
    }

    return d, "api/view-file", "post"

# d = cancel_all_open_orders()
# d = get_close_all_positions()
d , u, m = view_file()

url = f"http://{host}:{port}/{u}"
print(f"Sending request to {url}")
if  m == "post":
    resp = requests.post(
        url, json=d
    )
else:
    resp = requests.get(
        url
    )

print(d)
print(f"url:{url}")
print(f"Status:{resp.status_code}")
print(f"rest:{resp}")
print(f"Response:{resp.json()}")

print('# ###########################')
print('# ###########################')





if False:
    url = f"http://{host}:{port}/api/get-all-requests"

    resp = requests.get(url)

    print("Status:", resp.status_code)
    print("Body:", resp.json())


    print('# ###########################')
    print('# ###########################')



if True:

    url = f"http://{host}:{port}/api/health"
    print(f"Checking health at {url}")
    resp = requests.get(url)

    print("Status:", resp.status_code)
    print("Body:", resp.json())


    print('# ###########################')
    print('# ###########################')
