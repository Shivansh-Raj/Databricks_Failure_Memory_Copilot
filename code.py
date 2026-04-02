
@dlt.table(name="silver_users")
def silver_users():
    return spark.table("bronze_users")  # This won't work!