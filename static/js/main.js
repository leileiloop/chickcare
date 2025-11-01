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

//<!-- ========================= Notif ==================== -->

function toggleNotifi() {
    var box = document.getElementById('box');
    box.style.height = box.style.height === '0px' ? 'auto' : '0px';
    box.style.opacity = box.style.opacity === '0' ? '1' : '0';
}




//<!-- ========================= Date Time ==================== -->
function updateDateTime() {
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

//<!-- ========================= Temperature and Humidity Chart ==================== -->

// Initialize empty data arrays for the charts
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

//<!-- ========================= Manage Users ==================== -->

// admin.js - Functions for handling Edit and Delete actions in the Manage Users page

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
    //   .then(response => response.json())
    //   .then(data => {
    //     if(data.success) {
    //         // Optionally, refresh the table or remove the deleted row.
    //         location.reload();
    //     } else {
    //         alert("Deletion failed: " + data.message);
    //     }
    //   });
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
    let selectedUserId = null;  // Store selected user ID

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
            emailField.value = row.children[1].textContent;  // Email
            usernameField.value = row.children[2].textContent; // Username
            passwordField.value = row.children[3].textContent; // Password

            wrapper1.style.display = "flex"; // Show pop-up
        });

        closeBtn.addEventListener("click", function () {
            wrapper1.style.display = "none"; // Hide pop-up
        });
    }

    // Handle form submission
    if (submitBtn) {
        submitBtn.addEventListener("click", function (event) {
            event.preventDefault(); // Prevent default form submission

            if (!selectedUserId) {
                alert("No user selected for editing.");
                return;
            }

            // Prepare updated data
            const updatedData = {
                id: selectedUserId,
                email: emailField.value,
                username: usernameField.value,
                password: passwordField.value
            };

            // Send data to server for update
            fetch("/update_user", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(updatedData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("User updated successfully!");
                    wrapper.style.display = "none"; // Hide pop-up
                    location.reload(); // Refresh the page to show updated data
                } else {
                    alert("Update failed: " + data.message);
                }
            })
            .catch(error => console.error("Error updating user:", error));
        });
    }
});



//<!-- ========================= Manage Users Delete Btn ==================== -->

function deleteUser() {
    // Find the selected user via the radio button
    const selected = document.querySelector('input[name="selectedUser"]:checked');
    if (!selected) {
        alert("Please select a user to delete.");
        return;
    }
    const userId = selected.value;

    // Confirm deletion
    if (!confirm(`Are you sure you want to delete user ID ${userId}?`)) {
        return;
    }

    // Send request to delete user
    fetch(`/delete_user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: userId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert("User deleted successfully!");

            // Remove row from table
            const row = selected.closest("tr");
            row.parentNode.removeChild(row);
        } else {
            alert("Deletion failed: " + data.message);
        }
    })
    .catch(error => console.error("Error deleting user:", error));
}


//<!-- ========================= Report ==================== -->

document.addEventListener('DOMContentLoaded', function() {
  const recordTypeSelect = document.getElementById('recordType');

  // Hide all table containers
  function hideAllTables() {
    document.getElementById('tableGrowth').style.display = 'none';
    document.getElementById('tableGrowth1').style.display = 'none';
    document.getElementById('tableEnvironment').style.display = 'none';
    document.getElementById('tableSupplies').style.display = 'none';
    document.getElementById('tableNotifications').style.display = 'none';
    document.getElementById('tableSanitization').style.display = 'none';
  }

  // Show table based on dropdown selection
  function showTable(recordType) {
    hideAllTables();
    if (recordType === 'growth') {
      document.getElementById('tableGrowth').style.display = 'block';
    } else if (recordType === 'growth1') {
      document.getElementById('tableGrowth1').style.display = 'block';
    } else if (recordType === 'environment') {
      document.getElementById('tableEnvironment').style.display = 'block';
    } else if (recordType === 'supplies') {
      document.getElementById('tableSupplies').style.display = 'block';
    } else if (recordType === 'notifications') {
      document.getElementById('tableNotifications').style.display = 'block';
    } else if (recordType === 'sanitization') {
      document.getElementById('tableSanitization').style.display = 'block';
    }
  }

  // Listen for changes in the recordType dropdown
  recordTypeSelect.addEventListener('change', function() {
    showTable(this.value);
  });

  // Optionally, show 'All Record' by default or hide all by default
  showTable(recordTypeSelect.value);

  // Basic filter logic placeholders for search/date
  document.getElementById('searchBtn').addEventListener('click', () => {
    const keyword = document.getElementById('searchField').value;
    alert("Search for: " + keyword);
    // Implement search logic for whichever table is currently visible
  });

  document.getElementById('filterBtn').addEventListener('click', () => {
    const fromDate = document.getElementById('dateFrom').value;
    const toDate = document.getElementById('dateTo').value;
    alert(`Filter from: ${fromDate} to: ${toDate}`);
    // Implement date-range filter for the active table
  });
});

// Filtered Data Buttons

document.addEventListener("DOMContentLoaded", function () {
    // Select filter buttons
    const dailyBtn = document.getElementById("btnDaily");
    const weeklyBtn = document.getElementById("btnWeekly");
    const monthlyBtn = document.getElementById("btnMonthly");

    // Select record type dropdown
    const recordDropdown = document.getElementById("recordType");

    // Function to fetch data based on selected type and filter
    function fetchFilteredData(filterType) {
        const selectedRecord = recordDropdown.value; // Get selected record type

        switch (selectedRecord) {
            case "notifications":
                fetchNotifications(filterType);
                break;
            case "supplies":
                fetchSupplies(filterType);
                break;
            case "environment":
                fetchEnvironment(filterType);
                break;
            case "growth1":
                fetchGrowth(filterType);
                break;
            case "growth":
                fetchChickStatus(filterType);
                break;
            case "sanitization":
                fetchSanitization(filterType);
                break;
            default:
                console.warn("No valid record type selected");
        }
    }

    // Attach a single event listener for each button
    dailyBtn.addEventListener("click", () => fetchFilteredData("daily"));
    weeklyBtn.addEventListener("click", () => fetchFilteredData("weekly"));
    monthlyBtn.addEventListener("click", () => fetchFilteredData("monthly"));

    // Default to daily when dropdown is changed
    recordDropdown.addEventListener("change", () => fetchFilteredData("monthly"));
});


// Filtered Data

// Fetch Notifications Data (Daily, Weekly, Monthly)

// ========== FETCH FUNCTIONS ========== //
// Fetch Notifications Data
function fetchNotifications(filterType, limit = 20) {
    fetch(`/get_notifications_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableNotifications", ["DateTime", "message"]);
        })
        .catch(error => console.error("Error fetching notifications:", error));
}

// Fetch Supplies Data
function fetchSupplies(filterType, limit = 20) {
    fetch(`/get_supplies_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableSupplies", ["DateTime", "Food", "Water"]);
        })
        .catch(error => console.error("Error fetching supplies data:", error));
}

// Fetch Environment Data
function fetchEnvironment(filterType, limit = 20) {
    fetch(`/get_environment_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableEnvironment", ["DateTime", "Temperature", "Humidity", "Light1", "Light2", "Ammonia", "ExhaustFan"]);
        })
        .catch(error => console.error("Error fetching environment data:", error));
}

// Fetch Growth Tracking Data
function fetchGrowth(filterType, limit = 20) {
    fetch(`/get_growth_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableGrowth1", ["DateTime", "ChickNumber", "Weight", "WeighingCount", "AverageWeight"]);
        })
        .catch(error => console.error("Error fetching growth data:", error));
}

// Fetch Chick Status Data
function fetchChickStatus(filterType, limit = 20) {
    fetch(`/get_chickstatus_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableGrowth", ["DateTime", "ChickNumber", "status"]);
        })
        .catch(error => console.error("Error fetching chick status data:", error));
}

// Fetch Sanitization Data
function fetchSanitization(filterType, limit = 20) {
    fetch(`/get_sanitization_data1?filter=${filterType}`)
        .then(response => response.json())
        .then(data => {
            let limitedData = limitData(data, limit);
            updateTable(limitedData, "tableSanitization", ["DateTime", "Conveyor", "Sprinkle", "UVLight"]);
        })
        .catch(error => console.error("Error fetching sanitization data:", error));
}


// ========== HELPER FUNCTIONS ========== //
// Function to Update Tables Dynamically
function updateTable(data, tableId, columns) {
    let tableBody = document.querySelector(`#${tableId} tbody`);
    tableBody.innerHTML = ""; // Clear previous rows

    if (!data || data.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="${columns.length}">No data available</td></tr>`;
        return;
    }

    data.forEach(row => {
        let rowHTML = `<tr>`;
        columns.forEach(col => {
            rowHTML += `<td>${row[col] || "N/A"}</td>`;
        });
        rowHTML += `</tr>`;
        tableBody.innerHTML += rowHTML;
    });
}

// Function to Limit Data in JS (Show latest entries first)
function limitData(data, limit) {
    // Sort by DateTime if available (latest first)
    if (data.length > 0 && data[0].DateTime) {
        data.sort((a, b) => new Date(b.DateTime) - new Date(a.DateTime));
    }
    // Return only up to the limit
    return data.slice(0, limit);
}

//<!-- ========================= Report Search and Filter ==================== -->

document.addEventListener("DOMContentLoaded", function () {
    const searchBtn = document.getElementById("searchBtn");
    const filterBtn = document.getElementById("filterBtn");
    const searchField = document.getElementById("searchField");
    const dateFrom = document.getElementById("dateFrom");
    const dateTo = document.getElementById("dateTo");
    const recordDropdown = document.getElementById("recordType");

    // Function to fetch filtered data
    function fetchFilteredData() {
        const searchQuery = searchField.value.trim();
        const fromDate = dateFrom.value;
        const toDate = dateTo.value;
        const selectedRecord = recordDropdown.value;

        let url = `/get_filtered_data?recordType=${selectedRecord}&fromDate=${fromDate}&toDate=${toDate}&search=${searchQuery}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                console.log("API Response:", data);
                updateTable(data, selectedRecord);
            })
            .catch(error => console.error("Error fetching filtered data:", error));
    }

    // Add event listeners
    searchBtn.addEventListener("click", fetchFilteredData);
    filterBtn.addEventListener("click", fetchFilteredData);

    // ✅ Update table headers and rows dynamically
    function updateTable(data, recordType) {
        const tableId = getTableId(recordType);
        const table = document.getElementById(tableId);
        const thead = table.querySelector("thead");
        const tbody = table.querySelector("tbody");

        tbody.innerHTML = ""; // Clear body
        thead.innerHTML = ""; // Clear headers

        if (!data || data.length === 0) {
            thead.innerHTML = "<tr><th>No Data</th></tr>";
            tbody.innerHTML = `<tr><td colspan="5">No data available</td></tr>`;
            return;
        }

        // ✅ Dynamically generate headers from first row keys
        const headers = Object.keys(data[0]);
        let headerHTML = "<tr>";
        headers.forEach(header => {
            headerHTML += `<th>${header}</th>`;
        });
        headerHTML += "</tr>";
        thead.innerHTML = headerHTML;

        // ✅ Generate rows dynamically
        data.forEach(row => {
            let rowHTML = "<tr>";
            headers.forEach(key => {
                rowHTML += `<td>${row[key] !== undefined ? row[key] : "N/A"}</td>`;
            });
            rowHTML += "</tr>";
            tbody.innerHTML += rowHTML;
        });
    }

    // ✅ Function to match table IDs with record types
    function getTableId(recordType) {
        const tableMap = {
            "notifications": "tableNotifications",
            "supplies": "tableSupplies",
            "environment": "tableEnvironment",
            "growth": "tableGrowth",
            "growth1": "tableGrowth1",
            "sanitization": "tableSanitization"
        };
        return tableMap[recordType] || "tableAll";
    }
});






//<!-- ========================= Growth Poultry Image ==================== -->

function CaptureImage() {
         fetch('{{ url_for("tasks") }}', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'click=Capture',  // Adjust the data as needed
    })
    .then(response => response.json())
    .then(data => {
        // Handle the response if needed
        
    })
    .catch(error => {
        console.error('Error:', error);
    });
}


document.addEventListener("DOMContentLoaded", function() {
    updateLights();
});

//<!-- ========================= Env Changing Lights ==================== -->

function updateLights() {
    const lights = [
        { statusId: 'light1-status', imgId: 'light1', imgOn: '/static/imgs/LightO.png', imgOff: '/static/imgs/LightA.png' },
        { statusId: 'light2-status', imgId: 'light2', imgOn: '/static/imgs/LightO.png', imgOff: '/static/imgs/LightA.png' }
    ];

    lights.forEach(light => {
        const statusElement = document.getElementById(lights.statusId);
        const imgElement = document.getElementById(lights.imgId);

        if (statusElement.innerHTML === 'ON') {
            imgElement.src = lights.imgOn;
        } else {
            imgElement.src = lights.imgOff;
        }
    });
}


//<!-- ========================= Generate Notifications ==================== -->

//<!-- ========================= Supplies Stock ==================== -->

document.addEventListener('DOMContentLoaded', function () {
   

    loadNotifications();
    checkAndNotifyAll(arduinoDataJson); // Initial check

    // Check for new notifications periodically (simulate real-time updates)
    setInterval(checkLevels, 60000); // Check every 60 seconds
});

function checkLevels() {
    var waterLevelElement = document.getElementById("waterLevel");
    var foodLevelElement = document.getElementById("foodLevel");

    if (!waterLevelElement || !foodLevelElement) {
        console.error("Element not found: waterLevel or foodLevel");
        return;
    }

    var waterLevelText = waterLevelElement.innerText;
    var foodLevelText = foodLevelElement.innerText;

    let waterLevel = parseInt(waterLevelText.replace('%', ''));
    let foodLevel = parseInt(foodLevelText.replace('%', ''));

    let notifications = JSON.parse(localStorage.getItem('notifications')) || [];
    let newNotifications = [];

    // Water & Food Notifications
    if (waterLevel == 0) {
        newNotifications.push("🚨 Water is empty. Refill immediately!");
    } else if (waterLevel < 20) {
        newNotifications.push("⚠️ Water level is low. Consider refilling soon.");
    }

    if (foodLevel == 0) {
        newNotifications.push("🚨 Food is empty. Refill immediately!");
    } else if (foodLevel < 20) {
        newNotifications.push("⚠️ Food level is low. Consider refilling soon.");
    }

    fetch('/get_all_data5')
    .then(response => response.json())
    .then(data => {
        if (Array.isArray(data) && data.length > 0) {
            data.forEach(record => {
                if (record.status && !notifications.includes(record.status)) {
                    newNotifications.push(`🐔 Poultry Health Update: ${record.status}`);
                }
            });

            // Add only new notifications to avoid duplicates
            newNotifications.forEach(notification => {
                if (!notifications.includes(notification)) {
                    notifications.push(notification);
                }
            });

            localStorage.setItem('notifications', JSON.stringify(notifications));
            updateNotifications(notifications);
        } else {
            console.log("No new poultry health data found.");
        }
    })
    .catch(error => console.error("Error fetching poultry health data:", error));

}

function updateDashboardNotifications(notifications) {
    let notificationList = document.getElementById("notification-list");
    let notificationCount = document.getElementById("notification-count");

    // remove duplicates
    let uniqueNotifications = [...new Set(notifications)];

    // show only the latest 3
    let latestNotifications = uniqueNotifications.slice(-3).reverse();

    let unreadCount = uniqueNotifications.length;

    if (notificationList) {
        notificationList.innerHTML = '';
        latestNotifications.forEach(message => {
            let li = document.createElement("li");
            li.innerHTML = `<strong>System Alert:</strong> ${message}`;
            notificationList.appendChild(li);
        });
    }

    if (notificationCount) {
        notificationCount.innerText = unreadCount;
    }

}


function updateNotifications(notifications) {
    let notificationItems = document.getElementById("notificationItems");
    let notificationCount = document.getElementById("notificationCount");
    let notificationCount1 = document.getElementById("notificationCount1");

    let uniqueNotifications = removeDuplicates(notifications);
    let unreadCount = uniqueNotifications.length;

    if (notificationItems) {
        notificationItems.innerHTML = '';
        uniqueNotifications.forEach(message => {
            let notificationItem = document.createElement("div");
            notificationItem.classList.add("notifi-item");

            let notificationText = document.createElement("div");
            notificationText.classList.add("text");
            notificationText.innerHTML = `<h4>System Alert</h4><p>${message}</p>`;

            notificationItem.appendChild(notificationText);
            notificationItem.addEventListener('click', () => markAsRead(notificationItem, message));
            notificationItems.appendChild(notificationItem);

            // Send email for new notification
            sendEmailNotification(message);
        });
    }

    if (notificationCount) notificationCount.innerText = unreadCount;
    if (notificationCount1) notificationCount1.innerText = unreadCount;
    
     // **Also update the dashboard notifications**
    updateDashboardNotifications(uniqueNotifications);

    // **Send the latest notification to the backend**
    if (uniqueNotifications.length > 0) {
        fetch('/update_notification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notifications: uniqueNotifications })
        })
        .then(response => response.json())
        .then(data => console.log("Notification sent to backend:", data))
        .catch(error => console.error("Error sending notification to backend:", error));
    }
    
    
}

function sendEmailNotification(message) {
    fetch('/send_email_notification', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ message: message })
    }).then(response => response.json())
      .then(data => console.log(data))
      .catch(error => console.error('Error sending email:', error));
}

function removeDuplicates(notifications) {
    // Create a Set to store unique messages
    let uniqueMessages = new Set();

    // Filter out duplicate notifications
    return notifications.filter(notification => {
        if (uniqueMessages.has(notification)) {
            return false; // Skip if the notification is already in the set
        } else {
            uniqueMessages.add(notification);
            return true; // Keep unique notifications
        }
    });
}

function sendNotificationsToBackend(notifications) {
    const url = '/insert_notifications'; // Correct endpoint

    // Convert notifications to JSON format
    const data = JSON.stringify({ notifications });

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

//<!-- ========================= Environment ==================== -->

document.addEventListener('DOMContentLoaded', function () {
    

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

    var tempText = tempElement.innerText;
    var humText = humElement.innerText;
    var ammText = ammElement.innerText;

    let temperature = parseFloat(tempText.replace('°C', ''));
    let humidity = parseFloat(humText.replace('%', ''));
    let ammonia = parseFloat(ammText.replace('ppm', '')); // assuming "ppm" unit

    let notifications = JSON.parse(localStorage.getItem('notifications')) || [];
    let newNotifications = [];

    // Define thresholds
    const tempThreshold = 38;  // °C
    const humThreshold = 70;   // %
    const ammThreshold = 500;  // ppm

    if (temperature > tempThreshold) {
        newNotifications.push("Temperature is high. Take action to cool down.");
    }

    if (humidity > humThreshold) {
        newNotifications.push("Humidity is high. Take action to reduce moisture.");
    }

    if (ammonia > ammThreshold) {
        newNotifications.push("Ammonia level is high. Take action to improve air quality.");
    }

    // Add only new notifications to avoid duplicates
    newNotifications.forEach(notification => {
        if (!notifications.includes(notification)) {
            notifications.push(notification);
        }
    });

    localStorage.setItem('notifications', JSON.stringify(notifications));
    updateNotifications(notifications);
}

let waterLevel = 100;
let foodLevel = 100;
let temperature = 25;
let humidity = 50;

// Fetch or simulate updated sensor data every 60 seconds
function fetchData() {
    // Example fetch logic - replace with actual data source
    waterLevel = parseInt(document.getElementById("waterLevel")?.innerText.replace('%', '') || waterLevel);
    foodLevel = parseInt(document.getElementById("foodLevel")?.innerText.replace('%', '') || foodLevel);
    temperature = parseFloat(document.getElementById("temp")?.innerText.replace('°C', '') || temperature);
    humidity = parseFloat(document.getElementById("hum")?.innerText.replace('%', '') || humidity);
}

document.addEventListener('DOMContentLoaded', function () {
    

    loadNotifications();
    checkLevels(); // Initial check
    checkTempAndHumidity(); // Initial temperature and humidity check

    // Fetch new data and check for notifications every 60 seconds
    setInterval(() => {
        fetchData();
        checkLevels();
        checkTempAndHumidity();
    }, 4000);
});

// Existing checkLevels and checkTempAndHumidity functions can remain as they are

//<!-- =========================  ==================== -->

document.addEventListener('DOMContentLoaded', function () {
    

    loadNotifications();
    checkLevels(); // Initial check
    checkDeviceStatusesENV(); // Initial check for devices

    // Check for new notifications periodically (simulate real-time updates)
    setInterval(() => {
        checkLevels();
        checkDeviceStatusesENV(); // Check device statuses every 60 seconds
    }, 4000); // Check every 60 seconds
});

function checkDeviceStatusesENV() {
    let notifications = JSON.parse(localStorage.getItem('notifications')) || [];
    let newNotifications = [];

    for (let i = 1; i <= 4; i++) {
        const lightStatusElement = document.getElementById(`light${i}-status`);
        if (lightStatusElement) {
            const statusText = lightStatusElement.innerText.trim();
            if (statusText === "ON") {
                newNotifications.push(`Light ${i} is turned ON.`);
            } else if (statusText === "OFF") {
                newNotifications.push(`Light ${i} is turned OFF.`);
            }
        }
    }

    const exhaustFanStatusElement = document.getElementById("exhaustfan-status");
    if (exhaustFanStatusElement) {
        const exhaustFanStatus = exhaustFanStatusElement.innerText.trim();
        if (exhaustFanStatus === "ON") {
            newNotifications.push("Exhaust fan is turned ON.");
        } else if (exhaustFanStatus === "OFF") {
            newNotifications.push("Exhaust fan is turned OFF.");
        }
    }

    // Add only new notifications to avoid duplicates
    newNotifications.forEach(notification => {
        if (!notifications.includes(notification)) {
            notifications.push(notification);
        }
    });

    localStorage.setItem('notifications', JSON.stringify(notifications));
    updateNotifications(notifications);
}


//<!-- ========================= Sanitization ==================== -->


document.addEventListener('DOMContentLoaded', function () {
    

    loadNotifications();
    checkLevels(); // Initial check
    checkDeviceStatusesS(); // Initial check for devices

    // Check for new notifications periodically (simulate real-time updates)
    setInterval(() => {
        checkLevels();
        checkDeviceStatusesS(); // Check device statuses every 60 seconds
    }, 4000); // Check every 60 seconds
});

function checkDeviceStatusesS() {
    let notifications = JSON.parse(localStorage.getItem('notifications')) || [];
    let newNotifications = [];

    const devices = [
        { id: "status_cvyr", name: "Conveyor" },
        { id: "sprkl", name: "Sprinkle" },
        { id: "uvc_status", name: "UV Light" }
    ];

    devices.forEach(device => {
        const statusElement = document.getElementById(device.id);
        if (statusElement) {
            const statusText = statusElement.innerText.trim();
            if (statusText === "ON") {
                newNotifications.push(`${device.name} is turned ON.`);
            } else if (statusText === "OFF") {
                newNotifications.push(`${device.name} is turned OFF.`);
            }
        }
    });

    // Add only new notifications to avoid duplicates
    newNotifications.forEach(notification => {
        if (!notifications.includes(notification)) {
            notifications.push(notification);
        }
    });

    localStorage.setItem('notifications', JSON.stringify(notifications));
    updateNotifications(notifications);
}


//<!-- =========================  ==================== -->


//<!-- ========================= WEIGHT Arduino Data ==================== -->

// Function to fetch data for Weight and update the chart
function fetchData1() {
    fetch('/data') // Updated to fetch data from Flask server
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            

            if (
                data.Weight_1 !== undefined &&
                data.Weight_2 !== undefined &&
                data.Weight_3 !== undefined &&
                data.Weight_4 !== undefined &&
                data.Weight_5 !== undefined &&
                data.Weight_6 !== undefined

            ) {
            
                document.getElementById("weight").innerText = data.Weight_1.toFixed(2) + ' kg';
                document.getElementById("weight2").innerText = data.Weight_2.toFixed(2) + ' kg';
                document.getElementById("weight3").innerText = data.Weight_3.toFixed(2) + ' kg';
                document.getElementById("weight4").innerText = data.Weight_4.toFixed(2) + ' kg';
                document.getElementById("weight5").innerText = data.Weight_5.toFixed(2) + ' kg';
                document.getElementById("weight6").innerText = data.Weight_6.toFixed(2) + ' kg';


                
            } else {
                console.log("Some data is missing:", data);
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// Set an interval to fetch data every second for Weight
setInterval(fetchData1, 1000); // Fetch data every second

// ========================= Sanitization Data ====================

// Function to fetch sanitization data and update the chart
function fetchData2() {
    fetch('/data') // Updated to fetch data from Flask server
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            

            if (
                data.Conveyor !== undefined &&
                data.Sprinkle !== undefined &&
                data.UVLight !== undefined
            ) {

                document.getElementById("status_cvyr").innerText = (typeof data.Conveyor === 'number' ? data.Conveyor.toFixed(1) : data.Conveyor);
                document.getElementById("sprkl").innerText = (typeof data.Sprinkle === 'number' ? data.Sprinkle.toFixed(1) : data.Sprinkle);
                document.getElementById("uvc_status").innerText = (typeof data.UVLight === 'number' ? data.UVLight.toFixed(1) : data.UVLight);

            } else {
                console.log("Some data is missing:", data);
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// Set an interval to fetch sanitization data every second
setInterval(fetchData2, 1000); // Fetch data every second


function fetchData5() {
    fetch('/data') // Updated to fetch data from Flask server
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            

            if (
                data.UVLight !== undefined
            ) {

                document.getElementById("uvc_status").innerText = (typeof data.UVLight === 'number' ? data.UVLight.toFixed(1) : data.UVLight);

            } else {
                console.log("Some data is missing:", data);
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// Set an interval to fetch sanitization data every second
setInterval(fetchData5, 1000); // Fetch data every second

// ========================= Environment Table Data ====================
document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_all_data');
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
        const tableBody = document.querySelector('#table-body2 tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.Temperature || 'N/A'}</td>
                <td>${row.Humidity || 'N/A'}</td>
                <td>${row.Light1 || 'N/A'}</td>
                <td>${row.Light2 || 'N/A'}</td>
                <td>${row.Ammonia || 'N/A'}</td>
                <td>${row.ExhaustFan || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});

// ========================= Growth Tracking Table Data ====================
document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_all_data1');
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
        const tableBody = document.querySelector('#table-body1 tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.ChickNumber || 'N/A'}</td>
                <td>${row.Weight || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});

// ========================= Sanitization Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_all_data2');
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
        const tableBody = document.querySelector('#table-body tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.Conveyor || 'N/A'}</td>
                <td>${row.Sprinkle || 'N/A'}</td>
                <td>${row.UVLight || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});

// ========================= Supplies Table Data ====================

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
            populateTable(data);
        } catch (error) {
            console.error('Error fetching data:', error);
        }
    }

    // Function to populate the table with all data
    function populateTable(data) {
        const tableBody = document.querySelector('#table-users tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            console.log(row);
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td><input type="radio" name="selectedUser" value="${row.id}"></td>
                <td>${row.Email || 'N/A'}</td>
                <td>${row.Username || 'N/A'}</td>
                <td>${row.Password || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData6();
});

// ========================= Water and Food Level Data ====================

// Function to fetch data for Weight and update the chart
function fetchData3() {
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

                document.getElementById("waterLevel").innerText = data.Water_Level.toFixed(1) + ' %';
                document.getElementById("foodLevel").innerText = data.Food_Level.toFixed(1) + ' %';

            } else {
                console.log("Some data is missing:", data);
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

                updateWaterGauge(data.Water_Level);
                updateFoodGauge(data.Food_Level);

            } else {
                console.log("Some data is missing:", data);
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// Set an interval to fetch data every second for water and food levels
setInterval(fetchData4, 1000); // Fetch data every second


// ========================= All Record ====================


// ========================= Environment Table Data ====================
document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_environment_data');
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
        const tableBody = document.querySelector('#tableEnvironment tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.Temperature || 'N/A'}</td>
                <td>${row.Humidity || 'N/A'}</td>
                <td>${row.Light1 || 'N/A'}</td>
                <td>${row.Light2 || 'N/A'}</td>
                <td>${row.Ammonia || 'N/A'}</td>
                <td>${row.ExhaustFan || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});

// ========================= Growth Tracking Table Data ====================
document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_growth_data');
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
        const tableBody = document.querySelector('#tableGrowth1 tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.ChickNumber || 'N/A'}</td>
                <td>${row.Weight || 'N/A'}</td>
                <td>${row.WeighingCount || 'N/A'}</td>
                <td>${row.AverageWeight || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});


// ========================= Sanitization Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_sanitization_data');
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
        const tableBody = document.querySelector('#tableSanitization tbody');
        tableBody.innerHTML = ''; // Clear existing rows

        // Loop through all rows and create a row for each one
        data.forEach(row => {
            const tableRow = document.createElement('tr');
            tableRow.innerHTML = `
                <td>${row.DateTime || 'N/A'}</td>
                <td>${row.Conveyor || 'N/A'}</td>
                <td>${row.Sprinkle || 'N/A'}</td>
                <td>${row.UVLight || 'N/A'}</td>
            `;
            tableBody.appendChild(tableRow);
        });
    }

    // Fetch data on page load
    fetchData();
});

// ========================= Supplies Table Data ====================

document.addEventListener('DOMContentLoaded', function () {
    // Function to fetch data from the API
    async function fetchData() {
        try {
            const response = await fetch('/get_supplies_data');
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
        const tableBody = document.querySelector('#tableSupplies tbody');
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

// ========================= Sanitization Stop Button ====================

document.getElementById("stopConveyor").addEventListener("click", function () {
    sendStopCommand("STOP_CONVEYOR");
});

document.getElementById("stopUVLight").addEventListener("click", function () {
    sendStopCommand("STOP_UV_LIGHT");
});

document.getElementById("stopSprinkle").addEventListener("click", function () {
    sendStopCommand("STOP_SPRINKLE");
});

document.getElementById("light1").addEventListener("click", function () {
    sendStopCommand("STOP_LIGHT1");
});

document.getElementById("light2").addEventListener("click", function () {
    sendStopCommand("STOP_LIGHT2");
});

document.getElementById("light3").addEventListener("click", function () {
    sendStopCommand("STOP_LIGHT3");
});

document.getElementById("light4").addEventListener("click", function () {
    sendStopCommand("STOP_LIGHT4");
});

document.getElementById("stopServoFood").addEventListener("click", function () {
    sendStopCommand("STOP_SERVO_FOOD");
});

document.getElementById("stopWaterRelay").addEventListener("click", function () {
    sendStopCommand("STOP_WATER_RELAY");
});

document.getElementById("exhaustfan").addEventListener("click", function () {
    sendStopCommand("STOP_EXHAUST_FAN");
});


// Function to send the stop command to Flask
function sendStopCommand(command) {
    fetch("/stop_device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: command })
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message); // Show response message
    })
    .catch(error => console.error("Error stopping device:", error));
}


// Data CC Dashboard


function fetchData5() {
    fetch('/data') // Updated to fetch data from Flask server
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            

            if (
                data.Light1 !== undefined &&
                data.ExhaustFan !== undefined &&
                data.Temp !== undefined &&
                data.Hum !== undefined
            ) {

                document.getElementById("light-status-1").innerText = (typeof data.Light1 === 'number' ? data.Light1.toFixed(1) : data.Light1);
                document.getElementById("exhaust-fan-status").innerText = (typeof data.ExhaustFan === 'number' ? data.ExhaustFan.toFixed(1) : data.ExhaustFan);
                document.getElementById("temperature-value").innerText = (typeof data.Temp === 'number' ? data.Temp.toFixed(1) : data.Temp);
                document.getElementById("humidity-value").innerText = (typeof data.Hum === 'number' ? data.Hum.toFixed(1) : data.Hum);

            } else {
                console.log("Some data is missing:", data);
            }
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// Notif Dashboard Data

function fetchNotifications() {
    fetch('/get_all_data4')  // Request notification data
    .then(response => response.json())  // Convert response to JSON
    .then(data => {
        const notificationList = document.getElementById("notification-list");
        const notificationCount = document.getElementById("notification-count");

        if (!notificationList || !notificationCount) {
            console.error("Notification elements not found in the document.");
            return;
        }

        notificationList.innerHTML = "";  // Clear existing notifications

        if (data && Array.isArray(data) && data.length > 0) {
            data.forEach(notification => {
                let listItem = document.createElement("li");
                listItem.textContent = notification.message; // Display only the message
                notificationList.appendChild(listItem);
            });
            notificationCount.textContent = data.length; // Update notification count
        } else {
            notificationList.innerHTML = "<li>No new notifications</li>"; // Handle empty case
            notificationCount.textContent = "0";
        }

        // **SEND EMAIL ALERT WHEN NEW NOTIFICATION ARRIVES**
            fetch('/trigger_email_alert', { method: "POST" })
                .catch(error => console.error("Email alert failed:", error));

    })
    .catch(error => console.error("Error fetching notifications:", error));
}

// Ensure the script runs after the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function() {
    fetchNotifications();  // Fetch notifications on page load
    setInterval(fetchNotifications, 5000); // Auto-update every 5 seconds
});





































