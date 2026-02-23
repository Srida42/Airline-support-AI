CREATE DATABASE IF NOT EXISTS airline_support;
USE airline_support;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS flights (
    id INT AUTO_INCREMENT PRIMARY KEY,
    flight_number VARCHAR(10) NOT NULL,
    origin VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    departure_time DATETIME NOT NULL,
    arrival_time DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    flight_id INT,
    pnr VARCHAR(10) UNIQUE NOT NULL,
    seat_number VARCHAR(5),
    status ENUM('Confirmed', 'Cancelled', 'Checked-in') DEFAULT 'Confirmed',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (flight_id) REFERENCES flights(id)
);

CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT,
    issue_description TEXT,
    status ENUM('Open', 'In Progress', 'Resolved', 'Closed') DEFAULT 'Open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id)
);

CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Sample Data
INSERT INTO users (name, email, phone) VALUES ('John Doe', 'john@example.com', '1234567890');
INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time) 
VALUES ('AA123', 'New York (JFK)', 'London (LHR)', '2026-03-01 10:00:00', '2026-03-01 22:00:00');
INSERT INTO bookings (user_id, flight_id, pnr, seat_number) VALUES (1, 1, 'ABC123', '12A');
