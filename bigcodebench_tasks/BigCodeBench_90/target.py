import numpy as np
import math

def task_func(data, target, k):
    """
    Calculate the 'k' nearest neighbors by geographic coordinates using a dataset 
    and a target data point. The function returns a list of the 'k' nearest neighbors, 
    sorted in ascending order of their distances from the target.

    Parameters:
    data (DataFrame): The dataset containing geographical coordinates with columns ['Latitude', 'Longitude'].
    target (list): The target data point as [Latitude, Longitude].
    k (int): The number of nearest neighbors to return. Must be a non-negative integer.

    Returns:
    list: List of the 'k' nearest neighbors as [Latitude, Longitude].

    Raises:
    ValueError: If 'k' is a negative integer or not an integer.

    Constants:
    radius of earth is 6371 km

    Requirements:
    - numpy
    - math

    Example:
    >>> data = pd.DataFrame([[14, 25], [1, 22], [7, 8]], columns=['Latitude', 'Longitude'])
    >>> target = [10, 15]
    >>> k = 2
    >>> task_func(data, target, k)
    [[7, 8], [14, 25]]
    """
    if not isinstance(k, int) or k < 0:
        raise ValueError("'k' must be a non-negative integer")

    RADIUS_EARTH_KM = 6371.0  # Radius of the Earth in kilometers

    def calculate_distance(coord1, coord2):
        # Convert coordinates from degrees to radians
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return RADIUS_EARTH_KM * c

    distances = np.array([calculate_distance(target, coord) for coord in data.to_numpy()])
    nearest_indices = distances.argsort()[:k]
    nearest_neighbors = data.iloc[nearest_indices].values.tolist()

    return nearest_neighbors
