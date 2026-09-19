from sqlalchemy import func


def mysql_point(longitude: float, latitude: float):
    """Create SRID 4326 geometry with explicit conventional long/lat axis order."""
    wkt = f"POINT({longitude:.8f} {latitude:.8f})"
    return func.ST_GeomFromText(wkt, 4326, "axis-order=long-lat")


def distance_meters(column, longitude: float, latitude: float):
    return func.ST_Distance_Sphere(column, mysql_point(longitude, latitude))
