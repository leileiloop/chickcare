// add hovered class to selected list item
let list = document.querySelectorAll(".navigation li");

function activeLink() {
  list.forEach((item) => {
    item.classList.remove("hovered");
  });
  this.classList.add("hovered");
}

list.forEach((item) => item.addEventListener("mouseover", activeLink));

// Menu Toggle
let toggle = document.querySelector(".toggle");
let navigation = document.querySelector(".navigation");
let main = document.querySelector(".main");

toggle.onclick = function () {
  navigation.classList.toggle("active");
  main.classList.toggle("active");
};

//function toggleNotifi() {
  var box = document.getElementById('box');
  box.style.height = box.style.height === '0px' ? 'auto' : '0px';
  box.style.opacity = box.style.opacity === '0' ? '1' : '0';
}

//function updateDateTime() {
  // Get the current date and time
  var currentDateTime = new Date();

  // Format the date as YYYY-MM-DD
  var year = currentDateTime.getFullYear();
  var month = (currentDateTime.getMonth() + 1).toString().padStart(2, '0'); // Month is zero-based
  var day = currentDateTime.getDate().toString().padStart(2, '0');

  // Format the time as HH:MM:SS
  var hours = currentDateTime.getHours().toString().padStart(2, '0');
  var minutes = currentDateTime.getMinutes().toString().padStart(2, '0');
  var seconds = currentDateTime.getSeconds().toString().padStart(2, '0');

  // Display the formatted date and time in the span
  document.getElementById("displayDateTime").innerText = year + '-' + month + '-' + day + ' ' + hours + ':' + minutes + ':' + seconds;
}

// Update the time every second (1000 milliseconds)
setInterval(updateDateTime, 1000);

// Initial call to set the time immediately
updateDateTime();

//// Initialize empty data arrays for the charts
var dataTemperature = {
  labels: [],
  datasets: [{
    label: 'Temperature',
    borderColor: 'rgb(75, 192, 192)',
    data: [],
    fill: false
  }]
};

var dataHumidity = {
  labels: [],
  datasets: [{
    label: 'Humidity',
    borderColor: 'rgb(75, 192, 192)',
    data: [],
    fill: false
  }]
};

// Declare chart variables
var lineChartTemperature, lineChartHumidity;

// Function to add new data point to the temperature chart
function addDataTemperature(label, value) {
  dataTemperature.labels.push(label);
  dataTemperature.datasets[0].data.push(value);
  updateChart(lineChartTemperature, dataTemperature);
}

// Function to add new data point to the humidity chart
function addDataHumidity(label, value) {
  dataHumidity.labels.push(label);
  dataHumidity.datasets[0].data.push(value);
  updateChart(lineChartHumidity, dataHumidity);
}

// Function to update a chart
function updateChart(chart, data) {
  // Limit the number of data points to display (e.g., 10)
  var maxDataPoints = 10;
  while (data.labels.length > maxDataPoints) {
    data.labels.shift();
    data.datasets[0].data.shift();
  }
  chart.update();
}

// Set up charts after the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  // Temperature Chart
  var ctxTemperature = document.getElementById('lineChart');
  if (ctxTemperature) {
    ctxTemperature = ctxTemperature.getContext('2d');
    lineChartTemperature = new Chart(ctxTemperature, {
      type: 'line',
      data: dataTemperature,
      options: {
        scales: {
          x: [{
            type: 'linear',
            position: 'bottom'
          }]
        }
      }
    });
  } else {
    console.warn('Temperature chart canvas not found!');
  }

  // Humidity Chart
  var ctxHumidity = document.getElementById('lineChart1');
  if (ctxHumidity) {
    ctxHumidity = ctxHumidity.getContext('2d');
    lineChartHumidity = new Chart(ctxHumidity, {
      type: 'line',
      data: dataHumidity,
      options: {
        scales: {
          x: [{
            type: 'linear',
            position: 'bottom'
          }]
        }
      }
    });
  } else {
    console.warn('Humidity chart canvas not found!');
  }

  function fetchData() {
    fetch('/data') // Updated to fetch data from Flask server
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok ' + response.statusText);
        }
        return response.json();
      })
      .then(data => {
        if (
          data.Temp !== undefined &&
          data.Hum !== undefined &&
          data.Amm !== undefined &&
          data.Light1 !== undefined &&
          data.Light2 !== undefined &&
          data.ExhaustFan !== undefined
        ) {
          // Get current time as label for charts
          const label = new Date().toLocaleTimeString();

          // Update temperature and humidity charts (functions should be defined elsewhere)
          addDataTemperature(label, data.Temp);
          addDataHumidity(label, data.Hum);

          // Update temperature and humidity display
          document.getElementById("temp").innerText = `${data.Temp.toFixed(1)}°C`;
          document.getElementById("hum").innerText = `${data.Hum.toFixed(1)} %`;
          document.getElementById("amm").innerText = `${data.Amm.toFixed(1)} ppm`;

          document.getElementById("light1-status").innerText = data.Light1 === "ON" ? "ON" : "OFF";
          document.getElementById("light2-status").innerText = data.Light2 === "ON" ? "ON" : "OFF";
          document.getElementById("exhaustfan-status").innerText =
            data.ExhaustFan === "ON" ? "ON" : "OFF";
        } else {
          console.log("Some data is missing:", data);
        }
      })
      .catch(error => {
        console.error('Error fetching data:', error);
      });
  }

  // Fetch data every second
  setInterval(fetchData, 1000);

});

//// admin.js - Functions for handling Edit and Delete actions in the Manage Users page

function editUser() {
  // Find the selected user via the radio button
  const selected = document.querySelector('input[name="selectedUser"]:checked');
  if (!selected) {
    alert("Please select a user to edit.");
    return;
  }
  const userId = selected.value;
  // For demonstration purposes, we alert the user ID.
  // In a real application, you might open a modal or redirect to an edit page:
  // window.location.href = `/edit_user/${userId}`;
  alert("Edit user with ID: " + userId);
}

function deleteUser() {
  // Find the selected user via the radio button
  const selected = document.querySelector('input[name="selectedUser"]:checked');
  if (!selected) {
    alert("Please select a user to delete.");
    return;
  }
  const userId = selected.value;
  // Confirm deletion
  if (confirm("Are you sure you want to delete user ID " + userId + "?")) {
    // For demonstration purposes, we alert the deletion.
    // Replace this with your server-side logic (AJAX or fetch) to delete the user.
    alert("User " + userId + " deleted. (Implement server-side logic)");
    // Example using fetch:
    // fetch(`/delete_user/${userId}`, { method: 'POST' })
    // .then(response => response.json())
    // .then(data => {
    // if(data.success) {
    // // Optionally, refresh the table or remove the deleted row.
    // location.reload();
    // } else {
    // alert("Deletion failed: " + data.message);
    // }
    // });
  }
}

// ========================= Manage Users Edit Btn ====================

document.addEventListener("DOMContentLoaded", function () {
  const popBtn = document.querySelector(".popBtn");
  const closeBtn = document.querySelector(".close");
  const wrapper1 = document.querySelector(".wrapper1");
  const submitBtn = document.querySelector(".submit-edit");
  const emailField = document.getElementById("email");
  const usernameField = document.getElementById("username");
  const passwordField = document.getElementById("password");
  let selectedUserId = null; // Store selected user ID

  if (popBtn && closeBtn && wrapper1) {
    popBtn.addEventListener("click", function () {
      const selectedUser = document.querySelector('input[name="selectedUser"]:checked');
      if (!selectedUser) {
        alert("Please select a user to edit.");
        return;
      }

      // Store selected user ID
      selectedUserId = selectedUser.value;
      const row = selectedUser.closest("tr");
      emailField.value = row.children[1].textContent; // Email
      usernameField.value = row.children[2].textContent; // Username
      passwordField.value = ""; // Clear password field for security
      wrapper1.style.display = "block";
    });

    closeBtn.addEventListener("click", function () {
      wrapper1.style.display = "none";
    });

    window.addEventListener("click", function (event) {
      if (event.target === wrapper1) {
        wrapper1.style.display = "none";
      }
    });

    submitBtn.addEventListener("click", function (event) {
      event.preventDefault(); // Prevent form submission
      // Implement logic to update user data
      // For demonstration, log data to console
      console.log("Submit:", {
        id: selectedUserId,
        email: emailField.value,
        username: usernameField.value,
        password: passwordField.value, // Handle password updates securely
      });
      // In a real application, you would use fetch to send this data
      // to a Flask endpoint (e.g., /update_user/<id>)
      alert("Update logic to be implemented (see console).");
      wrapper1.style.display = "none";
    });
  }
});

// ========================= Notifications ====================

function addNotification(message) {
  let notifications = JSON.parse(localStorage.getItem('notifications')) || [];

  // Add the new notification
  notifications.push(message);

  // Store updated notifications
  localStorage.setItem('notifications', JSON.stringify(notifications));

  // Update the UI
  updateNotifications(notifications);

  // Send notifications to the backend
  sendNotificationsToBackend(notifications);
}

function updateNotifications(notifications) {
  const notiBox = document.getElementById('noti-box');
  const notiCount = document.getElementById('noti-count');

  if (!notiBox || !notiCount) {
    console.error("Notification box or count element not found.");
    return;
  }

  // Clear existing notifications
  notiBox.innerHTML = '';

  if (notifications.length === 0) {
    notiBox.innerHTML = '<li>No new notifications</li>';
    notiCount.textContent = '0';
    notiCount.style.display = 'none';
  } else {
    notifications.forEach(message => {
      const li = document.createElement('li');
      li.textContent = message;
      li.onclick = function () {
        markAsRead(li, message);
      };
      notiBox.appendChild(li);
    });
    notiCount.textContent = notifications.length;
    notiCount.style.display = 'block';
  }
}

function sendNotificationsToBackend(notifications) {
  // Define the backend endpoint URL
  const url = '/api/notifications'; // Replace with your Flask backend endpoint

  // Convert notifications to JSON format
  const data = JSON.stringify({
    notifications
  });

  fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: data,
    })
    .then(response => response.json())
    .then(data => {
      console.log("Notifications sent to backend successfully:", data);
    })
    .catch(error => {
      console.error("Error sending notifications to backend:", error);
    });
}

function loadNotifications() {
  const notifications = JSON.parse(localStorage.getItem('notifications')) || [];
  updateNotifications(notifications);
}

function markAsRead(notificationItem, message) {
  // Remove the notification visually
  notificationItem.classList.add("read");

  // Update notifications in storage
  let notifications = JSON.parse(localStorage.getItem('notifications')) || [];
  notifications = notifications.filter(notif => notif !== message);
  localStorage.setItem('notifications', JSON.stringify(notifications));

  // Update the notifications count
  updateNotifications(notifications);
}

//document.addEventListener('DOMContentLoaded', function () {
  loadNotifications();
  checkLevels(); // Initial check
  checkTempAndHumidity(); // Initial temperature and humidity check

  // Check for new notifications periodically (simulate real-time updates)
  setInterval(checkLevels, 60000); // Check every 60 seconds
  setInterval(checkTempAndHumidity, 60000); // Check every 60 seconds for temp and humidity
});

function checkTempAndHumidity() {
  var tempElement = document.getElementById("temp");
  var humElement = document.getElementById("hum");
  var ammElement = document.getElementById("amm");

  if (!tempElement || !humElement || !ammElement) {
    console.error("Element not found: temp, hum, or amm");
    return;
  }

  var temp = parseFloat(tempElement.innerText);
  var hum = parseFloat(humElement.innerText);
  var amm = parseFloat(ammElement.innerText);

  // Check temperature
  if (temp > 35) {
    addNotification("High Temperature Alert: " + temp + "°C");
  } else if (temp < 20) {
    addNotification("Low Temperature Alert: " + temp + "°C");
  }

  // Check humidity
  if (hum > 70) {
    addNotification("High Humidity Alert: " + hum + "%");
  } else if (hum < 50) {
    addNotification("Low Humidity Alert: " + hum + "%");
  }

  // Check ammonia
  if (amm > 25) {
    addNotification("High Ammonia Alert: " + amm + " ppm");
  }
}

function checkLevels() {
  var waterLevel = parseFloat(document.getElementById("waterLevel").innerText);
  var foodLevel = parseFloat(document.getElementById("foodLevel").innerText);

  if (waterLevel < 20) {
    addNotification("Water level is low: " + waterLevel + "%");
  }

  if (foodLevel < 20) {
    addNotification("Food level is low: " + foodLevel + "%");
  }
}

// ========================= Food/Water Stock Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData() {
    try {
      const response = await fetch('/get_all_data3');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable(data) {
    const tableBody = document.querySelector('#table-body3 tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td>${row.DateTime || 'N/A'}</td>
      <td>${row.Food || 'N/A'}</td>
      <td>${row.Water || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData();
});

// ========================= Notif Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData() {
    try {
      const response = await fetch('/get_all_data4');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable(data) {
    const tableBody = document.querySelector('#table-body4 tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td>${row.DateTime || 'N/A'}</td>
      <td>${row.Water_Level || 'N/A'}</td>
      <td>${row.Food_Level || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData();
});

// ========================= Environment Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData() {
    try {
      const response = await fetch('/get_all_data5');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable(data) {
    const tableBody = document.querySelector('#table-body5 tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td>${row.DateTime || 'N/A'}</td>
      <td>${row.ChickNumber || 'N/A'}</td>
      <td>${row.status || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData();
});

// ========================= Manage Users Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData6() {
    try {
      const response = await fetch('/get_all_data6');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable6(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable6(data) {
    const tableBody = document.querySelector('#table-body6 tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td><input type="radio" name="selectedUser" value="${row.id || 'N/A'}"></td>
      <td>${row.email || 'N/A'}</td>
      <td>${row.username || 'N/A'}</td>
      <td>${row.role || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData6();
});

// ========================= Notifications Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData() {
    try {
      const response = await fetch('/get_notifications_data');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable(data) {
    const tableBody = document.querySelector('#tableNotifications tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td>${row.DateTime || 'N/A'}</td>
      <td>${row.message || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData();
});

// ========================= Diagnostic Health Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data from the API
  async function fetchData() {
    try {
      const response = await fetch('/get_chickstatus_data');
      const data = await response.json();

      // Check if the data contains an error
      if (data.error) {
        console.error(data.error);
        return;
      }

      // Populate the table with all data
      populateTable(data);
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  }

  // Function to populate the table with all data
  function populateTable(data) {
    const tableBody = document.querySelector('#tableGrowth tbody');
    tableBody.innerHTML = ''; // Clear existing rows

    // Loop through all rows and create a row for each one
    data.forEach(row => {
      const tableRow = document.createElement('tr');
      tableRow.innerHTML = `
      <td>${row.DateTime || 'N/A'}</td>
      <td>${row.ChickNumber || 'N/A'}</td>
      <td>${row.status || 'N/A'}</td>
      `;
      tableBody.appendChild(tableRow);
    });
  }

  // Fetch data on page load
  fetchData();
});

// ========================= Weight and Supplies ====================

document.addEventListener('DOMContentLoaded', function () {
  // Function to fetch data and update Weight
  function fetchData3() {
    fetch('/get_growth_data')
      .then(response => response.json())
      .then(data => {
        // Check if data is an array and not empty
        if (Array.isArray(data) && data.length > 0) {
          // Get the latest data (first item in the array)
          const latestData = data[0];

          // Update the Weight
          if (latestData.Weight !== undefined) {
            document.getElementById("weight").innerText = `${latestData.Weight.toFixed(1)} g`;
          } else {
            console.log("Weight data is missing in the latest record:", latestData);
          }
        } else {
          console.log("No data received or data is empty.");
        }
      })
      .catch(error => {
        console.error('Error fetching data:', error);
      });
  }

  // Set an interval to fetch data every second for Weight
  setInterval(fetchData3, 1000); // Fetch data every second

  function updateWaterGauge(waterLevel) {
    const maxRotation = 180; // Maximum rotation degree for water gauge
    const rotation = (waterLevel / 100) * maxRotation; // Scale the water level to rotation range
    console.log(`Water Level: ${waterLevel}%, Rotation: ${rotation}°`); // Log rotation value

    // Apply the rotation to the fill element
    document.querySelector('.circle-wrap .circle .mask .fill').style.transform = `rotate(${rotation}deg)`;

    // Update the text inside the water gauge
    document.getElementById("waterLevel").innerText = waterLevel.toFixed(1) + ' %';
  }

  // Function to update the food gauge based on the fetched food level
  function updateFoodGauge(foodLevel) {
    // Ensure foodLevel is between 0 and 100
    if (foodLevel < 0) foodLevel = 0;
    if (foodLevel > 100) foodLevel = 100;

    // Calculate the degree of rotation for the food fill
    const maxRotation = 180; // Maximum rotation for a full gauge (100%)
    const rotation = (foodLevel / 100) * maxRotation; // Calculate the rotation based on the percentage

    // Apply rotation with a transition for smooth animation
    const foodFillElement = document.querySelector('.circle-wrap-1 .circle-1 .mask .fill-1');
    foodFillElement.style.transition = 'transform 0.5s ease-in-out'; // Ensure a smooth transition
    foodFillElement.style.transform = `rotate(${rotation}deg)`;

    // Update the text inside the food gauge
    document.getElementById("foodLevel").innerText = foodLevel.toFixed(1) + ' %';
  }

  // Water and Food Gauge Update Data

  function fetchData4() {
    fetch('/data') // Updated to fetch data from Flask server
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok ' + response.statusText);
        }
        return response.json();
      })
      .then(data => {
        if (
          data.Water_Level !== undefined &&
          data.Food_Level !== undefined
        ) {
          // Update water and food gauges
          updateWaterGauge(data.Water_Level);
          updateFoodGauge(data.Food_Level);
        } else {
          console.log("Water or Food Level data is missing:", data);
        }
      })
      .catch(error => {
        console.error('Error fetching data:', error);
      });
  }

  // Set an interval to fetch data every second
  setInterval(fetchData4, 1000);
});
