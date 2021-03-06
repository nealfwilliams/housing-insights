# -*- coding: utf-8 -*-

"""
flask api
~~~~~~~~~
This is a simple Flask applicationlication that creates SQL query endpoints.

"""

from flask import Flask, jsonify, request, Response, abort, json

import psycopg2
from sqlalchemy import create_engine

import logging
from flask_cors import CORS, cross_origin


#######################
# Setup
#######################
logging.basicConfig(level=logging.DEBUG)
application = Flask(__name__)

#Allow cross-origin requests. TODO should eventually lock down the permissions on this a bit more strictly, though only allowing GET requests is a good start.
CORS(application, resources={r"/api/*": {"origins": "*"}}, methods=['GET'])

with open('secrets.json') as f:
    secrets = json.load(f)
    connect_str = secrets['remote_database']['connect_str']


#Should create a new connection each time a separate query is needed so that API can recover from bad queries
#Engine is used to create connections in the below methods
engine = create_engine(connect_str)

#Establish a list of tables so that we can validate queries before executing
conn = engine.connect()
q = "SELECT tablename FROM pg_catalog.pg_tables where schemaname = 'public'"
proxy = conn.execute(q)
results = proxy.fetchall()
tables = [x[0] for x in results]
application.logger.debug('Tables available: {}'.format(tables))

##########################################
# API Endpoints
##########################################

@application.route('/')
def hello():
    return("The Housing Insights API Rules!")

@application.route('/api/raw/<table>', methods=['GET'])
def list_all(table):
    """ Generate endpoint to list all data in the tables. """

    application.logger.debug('Table selected: {}'.format(table))
    if table not in tables:
        application.logger.error('Error:  Table does not exist.')
        abort(404)

    #Query the database
    conn = engine.connect()
    q = 'SELECT row_to_json({}) from {} limit 1000;'.format(table, table)
    proxy = conn.execute(q)
    results = [x[0] for x in proxy.fetchmany(1000)] # Only fetching 1000 for now, need to implement scrolling
    #print(results)

    return jsonify(items=results)


@application.route('/api/<data_source>/all/<grouping>', methods=['GET'])
def count_all(data_source,grouping):
    """ Example endpoint of doing a COUNT on a specific zipcode. """


    #input validation so users only execute valid queries
    if grouping not in ['zipcode','ward','anc', 'neighborhood_cluster']:
        return jsonify({'items': None})
    if data_source not in ['building_permits', 'crime']:
        return jsonify({'items': None})


    application.logger.debug('Getting all {}'.format(grouping))

    #Determine some parameters based on user submissions
    #TODO this approach will get unwieldy soon - temporary quick approach
    #date field name varies by data_source
    date_fields = {'building_permits': 'issue_date', 'crime': 'report_date'}
    date_field = date_fields[data_source]
    fallback = "'Unknown'"

    try:
        conn = engine.connect()

        q = """
            SELECT COALESCE({},{}) --'Unknown'
            ,count(*) AS records
            FROM {}
            where {} between '2016-01-01' and '2016-12-31'
            --WHERE report_date BETWEEN (now()::TIMESTAMP - INTERVAL '1 year') AND now()::TIMESTAMP
            GROUP BY {} 
            ORDER BY {}
            """.format(grouping,fallback,data_source,date_field,grouping,grouping)

        proxy = conn.execute(q)
        results = proxy.fetchall()

        #transform the results.
        #TODO should come up with a better generic way to do this using column
          #names for any arbitrary sql table results. 
        formatted = []
        for x in results:
            dictionary = dict({'group':x[0], 'count':x[1]})
            formatted.append(dictionary)


        conn.close()
        return jsonify({'items': formatted, 'grouping':grouping, 'table':data_source})

    #TODO do better error handling - for interim development purposes only
    except Exception as e:
        #conn.close()
        return "Query failed: {}".format(e)



##########################################
# Start the app
##########################################

if __name__ == "__main__":
    try:
        application.run(host="0.0.0.0", debug=True)
    except:
        conn.close()
