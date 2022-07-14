from babytracker import web

DEBUG = False
web.app.run_server(debug=DEBUG, host='0.0.0.0')
