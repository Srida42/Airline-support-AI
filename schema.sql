-- ============================================================
-- Airline Support System - Sprint 1 Schema
-- ============================================================

CREATE DATABASE IF NOT EXISTS airline_support;
USE airline_support;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Flights table with seat availability tracking
CREATE TABLE IF NOT EXISTS flights (
    id INT AUTO_INCREMENT PRIMARY KEY,
    flight_number VARCHAR(10) NOT NULL UNIQUE,
    origin VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    departure_time DATETIME NOT NULL,
    arrival_time DATETIME NOT NULL,
    total_seats INT NOT NULL DEFAULT 150,
    available_seats INT NOT NULL DEFAULT 150,
    price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    status ENUM('Scheduled', 'Delayed', 'Cancelled', 'Completed') DEFAULT 'Scheduled',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_seats CHECK (available_seats >= 0 AND available_seats <= total_seats)
);

-- Bookings table with status tracking
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    flight_id INT NOT NULL,
    pnr VARCHAR(10) UNIQUE NOT NULL,
    seat_number VARCHAR(5),
    booking_status ENUM('Confirmed', 'Cancelled', 'Checked-in', 'Pending') DEFAULT 'Confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY (flight_id) REFERENCES flights(id) ON DELETE RESTRICT
);

-- Support tickets table
CREATE TABLE IF NOT EXISTS tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    issue_description TEXT NOT NULL,
    ticket_status ENUM('Open', 'In Progress', 'Resolved', 'Closed') DEFAULT 'Open',
    priority ENUM('Low', 'Medium', 'High', 'Urgent') DEFAULT 'Medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE RESTRICT
);

-- Action logs table
CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================
-- Stored Procedures for atomic operations
-- ============================================================

DELIMITER //

-- Procedure: Create booking (validates seat availability atomically)
CREATE PROCEDURE create_booking(
    IN p_user_id INT,
    IN p_flight_id INT,
    IN p_pnr VARCHAR(10),
    IN p_seat_number VARCHAR(5),
    OUT p_result VARCHAR(255)
)
BEGIN
    DECLARE v_available INT;
    
    START TRANSACTION;
    
    -- Lock the flight row for update
    SELECT available_seats INTO v_available 
    FROM flights WHERE id = p_flight_id FOR UPDATE;
    
    IF v_available IS NULL THEN
        SET p_result = 'ERROR: Flight not found';
        ROLLBACK;
    ELSEIF v_available <= 0 THEN
        SET p_result = 'ERROR: No seats available';
        ROLLBACK;
    ELSE
        -- Reduce available seats
        UPDATE flights SET available_seats = available_seats - 1 WHERE id = p_flight_id;
        
        -- Create booking
        INSERT INTO bookings (user_id, flight_id, pnr, seat_number)
        VALUES (p_user_id, p_flight_id, p_pnr, p_seat_number);
        
        SET p_result = 'SUCCESS';
        COMMIT;
    END IF;
END //

-- Procedure: Cancel booking (restore seat count atomically)
CREATE PROCEDURE cancel_booking(
    IN p_pnr VARCHAR(10),
    OUT p_result VARCHAR(255)
)
BEGIN
    DECLARE v_booking_id INT;
    DECLARE v_flight_id INT;
    DECLARE v_status VARCHAR(20);
    
    START TRANSACTION;
    
    SELECT b.id, b.flight_id, b.booking_status 
    INTO v_booking_id, v_flight_id, v_status
    FROM bookings b WHERE b.pnr = p_pnr FOR UPDATE;
    
    IF v_booking_id IS NULL THEN
        SET p_result = 'ERROR: Booking not found';
        ROLLBACK;
    ELSEIF v_status = 'Cancelled' THEN
        SET p_result = 'ERROR: Booking already cancelled';
        ROLLBACK;
    ELSEIF v_status = 'Checked-in' THEN
        SET p_result = 'ERROR: Cannot cancel a checked-in booking';
        ROLLBACK;
    ELSE
        UPDATE bookings SET booking_status = 'Cancelled' WHERE id = v_booking_id;
        UPDATE flights SET available_seats = available_seats + 1 WHERE id = v_flight_id;
        SET p_result = 'SUCCESS';
        COMMIT;
    END IF;
END //

DELIMITER ;

-- ============================================================
-- Sample Data
-- ============================================================

INSERT INTO users (name, email, phone) VALUES
    ('John Doe', 'john@example.com', '1234567890'),
    ('Jane Smith', 'jane@example.com', '9876543210'),
    ('Alice Johnson', 'alice@example.com', '5551234567');

INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, total_seats, available_seats, price) VALUES
    ('AA101', 'New York (JFK)', 'London (LHR)', '2026-04-01 08:00:00', '2026-04-01 20:00:00', 180, 42, 549.99),
    ('AA202', 'Los Angeles (LAX)', 'Chicago (ORD)', '2026-04-02 09:30:00', '2026-04-02 15:30:00', 150, 87, 199.99),
    ('AA303', 'Chicago (ORD)', 'Miami (MIA)', '2026-04-03 14:00:00', '2026-04-03 18:30:00', 150, 0, 249.99),
    ('AA404', 'London (LHR)', 'Dubai (DXB)', '2026-04-04 22:00:00', '2026-04-05 08:00:00', 200, 115, 399.99),
    ('AA505', 'New York (JFK)', 'Paris (CDG)', '2026-04-05 19:00:00', '2026-04-06 08:30:00', 200, 63, 629.99);

INSERT INTO bookings (user_id, flight_id, pnr, seat_number, booking_status) VALUES
    (1, 1, 'ABC123', '12A', 'Confirmed'),
    (2, 2, 'DEF456', '7B',  'Confirmed'),
    (3, 4, 'GHI789', '22C', 'Checked-in'),
    (1, 2, 'JKL012', '15D', 'Cancelled');

INSERT INTO tickets (booking_id, issue_description, ticket_status, priority) VALUES
    (1, 'Meal preference not recorded - requested vegetarian', 'Open', 'Medium'),
    (2, 'Baggage allowance query for international connection', 'Resolved', 'Low');