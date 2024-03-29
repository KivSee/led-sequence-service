# led-sequence-service

This service is part of the Kivsee led show and home lightning eco-system.

## Usage
Install dependencies: `pipenv install`.
Run the service: `pipenv run python led_sequence/main.py`

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

### Config
The config endpoint allows to get and put high level configuration parameters for a trigger.
This configuration can be used to create audacity labels and effects

- PUT `/triggers/{trigger_name}/config` - upsert config for a trigger. Payload should be `application/json` with following structure:
```json
{
    "bpmSections": [
        {
            "startSeconds": 0.09,
            "bpm": 67,
            "beatsPerEpisode": 32,
            "numEpisodes": 4
        },
        {
            "startSeconds": 114.830,
            "bpm": 78,
            "beatsPerEpisode": 16,
            "numEpisodes": 15

        }
    ],
    "lengthSeconds": 295
}
```

- GET `/triggers/{trigger_name}/config` - return the latest config for the trigger, as givin in PUT.

### Audacity Lables

The following endpoints return audacity compaitble text which can be saved to a file and loaded into audacity as import->labels. These give visual marks to aid synchronization.

- GET `/triggers/{trigger_name}/config/audacity/episodes` - this indicates the position of episodes in the track

- GET `/triggers/{trigger_name}/config/audacity/beats` - this indicates the position of beats in the track


### Sequence:
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

- PUT `/triggers/{trigger_name}` - Same as above, but update all the thing-objects at once. the payload is a json object, where keys are thing names, and values are json equivalent of AnimationProto like above endpoint. Example:
```json
{
	"foo": {
	    "effects": [{
	    	"effect_config": {
	    		"start_time": 0,
	    		"end_time": 200,
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
    },
    "bar": {
	    "effects": [{
	    	"effect_config": {
	    		"start_time": 600,
	    		"end_time": 800,
	    		"segments": "all"
	    	},
	    	"const_color": {
	    		"color": {
	    			"hue": 0.2,
	    			"sat": 0.7,
	    			"val": 1.0
	    		}
	    	}
	    }
	    ],
	    "duration_ms": 1000,
	    "num_repeats": 0        
    }
}
```

- GET `/triggers/{trigger_name}` - get all the sequences of a specific trigger for all objects. repose is a json map where key is object name and value is the sequence for that object. guid is returned on etag header.

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
