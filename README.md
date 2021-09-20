# led-sequence-service

This service is part of the Kivsee led show and home lightning eco-system.

## Usage
Install dependencies: `pipenv install`.
Run the service: `pipenv run led_sequence/main.py`

### Development
For developemnt, you can use `nodemon` to automatically restart the execution when code files are saved.
1. Install nodemon: `npm install --global nodemon`.
2. Enter the pipenv shell: `pipenv shell`
3. Run the service with nodemon which watch for file changes and relaunch the app: `nodemon led_sequence/main.py`

## Logging
You can set log level via environment variable `LOGLEVEL`. Default value is `INFO` and you can set any level from this list: `["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"]`

## REST API
LED sequences can be modified and queried via REST API.
To set the port for the http server, use environment variable:
```
SERVER_PORT=8082
```

### Endpoints:
- PUT `/triggers/{trigger_name}/objects/{thing_name}` - upsert sequence for a trigger on an object. Payload should be `application/json` matching to AnimationProto message. Example payload:
```json
{
    "effects": [{
    	"effect_config": {
    		"start_time": 0,
    		"end_time": 500,
    		"segments": "all"
    	},
    	"const_color": {
    		"color": {
    			"hue": 1.0,
    			"sat": 1.0,
    			"val": 0.3
    		}
    	}
    }
    ],
    "duration_ms": 1000,
    "num_repeats": 0
}
```

- GET `/triggers/{trigger_name}/objects/{thing_name}` - get sequence for `trigger_name` on object with `thing_name`. You can set `Content-Type` to either `application/json` or `application/x-protobuf`. 

- GET `/triggers/{trigger_name}/objects/{thing_name}/guid/{guid}` - Same as above, but return sequence with a specific `guid` and return 404 if guid is not found.

## Storage
The storage for objects can be configured via environment variables. Currently only git storge is supported.

### Git Storage
Git storage uses a local directory to store JSON files with the objects and configuration. It is the user's responsibility to create this directory, init it as the git repo, and sync it to remote origin.

To use git storage, set the following env variables:
```
STORAGE_TYPE=git
GIT_STORAGE_REPO=/path/to/git/directory
```
