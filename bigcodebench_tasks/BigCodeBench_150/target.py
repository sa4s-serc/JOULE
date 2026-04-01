import pandas as pd
import numpy as np


def task_func(product_dict, product_keys):
    """
    Create a profit report for a list of products based on a specific product dictionary that includes the quantity,
    price, and profit of each product. Additionally, calculate the average price and profit for all considered products,
    and plot a bar chart of the profit for each product.

    Parameters:
    - product_dict (dict): The dictionary containing product details with product name as key and a list
    [quantity, price] as value.
    - product_keys (list): The list of product keys to consider for the report.

    Returns: tuple: A tuple containing:
    - DataFrame: A pandas DataFrame with columns
    ['Product', 'Quantity', 'Price', 'Profit', 'Average Price', 'Average Profit'].
    - Axes: A matplotlib Axes object representing the plotted bar chart of profit for each product
    (None if no products).

    Requirements:
    - pandas
    - numpy

    Example:
    >>> product_dict = {'Apple': [100, 2.5], 'Orange': [80, 3.5], 'Banana': [120, 1.5]}
    >>> product_keys = ['Apple', 'Banana']
    >>> report, ax = task_func(product_dict, product_keys)
    >>> print(report)
      Product  Quantity  Price  Profit  Average Price  Average Profit
    0   Apple       100    2.5   250.0            2.0           215.0
    1  Banana       120    1.5   180.0            2.0           215.0

    """
    columns = ['Product', 'Quantity', 'Price', 'Profit']
    data = []

    for key in product_keys:
        quantity, price = product_dict[key]
        profit = quantity * price
        data.append([key, quantity, price, profit])

    df = pd.DataFrame(data, columns=columns)

    if not df.empty:
        # Calculate average price and average profit using numpy
        avg_price = np.mean(df['Price'])
        avg_profit = np.mean(df['Profit'])

        # Add average price and average profit as new columns to the dataframe
        df['Average Price'] = avg_price
        df['Average Profit'] = avg_profit

        ax = df.plot(x='Product', y='Profit', kind='bar', legend=False, title="Profit for each product")
        ax.set_ylabel("Profit")
    else:
        ax = None

    return df, ax
