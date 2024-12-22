# Building a webapp in Django for device and data management via Web Interface

## Overview
### Main purpose of the webapp
The app is designed to manage and monitor Modbus-based devices within a networked environment. Its main functionalities are:
<ul>
  <li><strong>Device Management </strong>: The app allows users to register, configure and control devices connected to a gateway. It provides a centralized interface for viewing device status, managing settings and performing actions on each device.</li>
  <li><strong>Modbus Communication </strong>: It supports scanning and interacting with modbus devices, reading data from Modbus registers, and mapping raw data to to meaningful physical values.</li>
  <li><strong>Real-time Data Monitoring </strong>: The app continuously collects and display data from connected device, and save them in a database. The data can be then viewed through the admin interface or through the dedicate page of the device's owner.</li>
  <li><strong>GPIO Control over SSH </strong>: Users and admins can interact with the gateway by controlling GPIO pins through customizable buttons on the webapp</li>
  <li><strong>Dedicated User Section</strong>:The app features a login system that distinguishes between regular users and admins. Users can login and view their device and related data in a dedicated page.</li>
  <li><strong>Admin Interface</strong>: Admins have an intuitive interface where they can configure device parameters, setup modbus addresses, manage variables and perform actions like creating new button and toggling them.</li>
</ul>

### Tech Stack
<ul>
  <li><strong>Backend Framework </strong>: Django</li>
  <li><strong>Database </strong>: PostgreSQL</li>
  <li><strong>Asynchronous Task Management </strong>: Celery (for handling background tasks), Redis (as message broker for Celery)</li>
  <li><strong>Frontend </strong>: HTML, CSS, Javascript, Django </li>
  <li><strong>Containerization> </strong>: Docker</li>
</ul>

### Architecture

## How to run the webapp
The app can be run in Debug mode by downloading the repository and typing the command 'docker-compose up -d --build'. Then it is possible to access the admin interface at 'http://localhost:8000/admin/'. 
To run the app in production mode it is necessary to install and configure a web server, like Apache2.

## Next steps
<ul>
  <li> Improve the user's page graphics </li>
  <li> Adding unit test </li>
  <li> Include a web server like Apache or Nginx for serving the webapp with Docker </li>
</ul>