import mysql.connector

# Establish connection to the database
mydb = mysql.connector.connect(
  host="localhost",
  user= os.getenv("QP_USER_NAME"),
  password= os.getenv("QP_PASSWORD"),
  database="mydatabase"
)

def updatedb(data):
    #Create a cursor object to execute queries
    mycursor = mydb.cursor()
    # Define the SQL quALTERery to insert data into the trades table
    sql = "INSERT INTO trades (user, Stock, quantity, AVG_price, type, AVG_cost, status) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    # Execute the query for each set of data
    mycursor.executemany(sql, data)   
    # Commit the changes to the database
    mydb.commit()
    # Print the number of rows inserted
    print(mycursor.rowcount, "rows inserted.")
    # Close the cursor and connection
    mycursor.close()

def get_user_credentials(username):
    # Establish connection to the MySQL database
    # Replace 'your_host', 'your_username', 'your_password', and 'your_database' with your actual database credentials
    connection = mydb
    # Create a cursor object to execute SQL queries
    cursor = connection.cursor()
    # Define the SQL query to retrieve username and password from the users table
    sql_query = "SELECT username, password FROM users WHERE username = %s"
    # Execute the SQL query
    cursor.execute(sql_query, (username,))
    # Fetch all rows from the result set
    results = cursor.fetchone()
    # Close cursor and connection
    cursor.close()
    # Return the results
    return results

def get_executed_orders(user):
    # Create a cursor object to execute queries
    mycursor = mydb.cursor(dictionary=True)
    # Execute the query to fetch data from the trades table
    mycursor.execute("SELECT * FROM trades WHERE user = %s", (user,))
    # Fetch all rows of the result
    data = mycursor.fetchall()
    # Close the cursor
    mycursor.close()
    return data