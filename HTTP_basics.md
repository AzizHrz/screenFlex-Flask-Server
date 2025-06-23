## GET Request
Purpose: Retrieve data from the server.

#### Characteristics:

Data is sent as query parameters in the URL.
It is used for read-only operations and should not have side effects on the server.
URL Example:
```bash
http://example.com/api?key=value&number=123
```
Data Limit: Limited by the maximum URL length supported by the browser or server.
Use Case: Fetching data, such as loading a webpage or querying a database.
- Example with Flask:

```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/get-data', methods=['GET'])
def get_data():
    data = request.args  # Retrieve query parameters
    print("Received GET data:", data)
    return jsonify({"message": "Data received", "data": data.to_dict()}), 200
```
- Send GET request with curl:

```bash
    curl "http://127.0.0.1:5000/get-data?key=value&number=123"
```

###### processing Get data 
```python
@app.route('/data', methods=['GET'])
def get_data():
    # Extract query parameters
    name = request.args.get('name', default='Guest', type=str)
    age = request.args.get('age', default=None, type=int)

    # Validate the parameters
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if age is not None and age < 0:
        return jsonify({"error": "Age cannot be negative"}), 400

    # Generate meaningful data to return
    response_data = {
        "message": f"Hello, {name}!",
        "age_info": f"Your age is {age}" if age else "Age not provided",
    }
    return jsonify(response_data), 200 

```
## POST Request
Purpose: Send data to the server, usually to create or update resources.

#### Characteristics:

Data is sent in the request body, not in the URL.
It can have side effects (e.g., creating a database entry, uploading a file).
Use Case: Submitting forms, uploading data, or sending JSON payloads.
- Example with Flask:

```python
@app.route('/post-data', methods=['POST'])
def post_data():
    data = request.get_json()  # Retrieve JSON data from the body
    print("Received POST data:", data)
    return jsonify({"message": "Data received", "data": data}), 200
```
- Send POST request with curl:

```bash
curl -X POST http://127.0.0.1:5000/post-data -H "Content-Type: application/json" -d '{"key":"value", "number":123}'
```
- Summary Table:

| **HTTP Method**  | **Purpose**          | **Data Location**            | **Use Case**                    |
|------------------|----------------------|------------------------------|---------------------------------|
| GET              | Retrieve data        | Query parameters in the URL  | Fetching data, loading pages    |
| POST             | Send data to server  | Request body                 | Submitting forms, creating data |


#### Which to Use?
- Use GET if the operation does not change the server state and is idempotent (e.g., fetching data).
- Use POST if you are sending data that modifies the server state (e.g., adding a new record).