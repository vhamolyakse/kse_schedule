# Use an OpenJDK base image with OpenJDK 11
FROM openjdk:11

# Set the working directory in the container
WORKDIR /usr/src/app

# Install Python 3.8
RUN apt-get update && \
    apt-get install -y python3.9 python3-pip && \
    apt-get clean;

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define environment variable
ENV NAME World

# Run app.py when the container launches
CMD ["streamlit", "run", "app.py"]
