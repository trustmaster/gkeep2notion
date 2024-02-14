FROM rcdeoliveira/gkeepapi
# Set the working directory to home folder
WORKDIR /home
# Copy necessary files into the container
COPY config.ini gkeep2notion.py requirements.txt /home/
# Set the entry point to bash
CMD ["bash"]