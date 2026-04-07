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
-- Professional Sample Data
-- ============================================================

-- Users with diverse Indian and international names
INSERT INTO users (name, email, phone) VALUES
    ('Rajesh Kumar Sharma', 'rajesh.sharma@email.com', '+91 98765 43210'),
    ('Priya Mehta', 'priya.mehta@email.com', '+91 99887 66554'),
    ('Aarav Singhania', 'aarav.singhania@email.com', '+91 87654 32109'),
    ('Dr. Sneha Reddy', 'sneha.reddy@email.com', '+91 88997 76655'),
    ('Vikram Malhotra', 'vikram.malhotra@email.com', '+91 99008 87766'),
    ('Neha Kapoor', 'neha.kapoor@email.com', '+91 98765 12345'),
    ('Arjun Nair', 'arjun.nair@email.com', '+91 99876 54321'),
    ('Fatima Khan', 'fatima.khan@email.com', '+91 87654 98765'),
    ('Rohan Deshmukh', 'rohan.deshmukh@email.com', '+91 99000 11122'),
    ('Ananya Banerjee', 'ananya.banerjee@email.com', '+91 98765 44332'),
    ('Michael Chen', 'michael.chen@email.com', '+1 (415) 555-0123'),
    ('Sarah Williams', 'sarah.williams@email.com', '+44 20 7946 0123'),
    ('Takeshi Yamamoto', 'takeshi.yamamoto@email.com', '+81 3 1234 5678'),
    ('Maria Garcia', 'maria.garcia@email.com', '+34 612 345 678'),
    ('David O\'Brien', 'david.obrien@email.com', '+353 1 234 5678');

-- Flights with realistic Indian and international routes
INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, total_seats, available_seats, price) VALUES
    ('AI101', 'Mumbai (BOM)', 'Delhi (DEL)', '2026-04-15 06:00:00', '2026-04-15 08:15:00', 180, 23, 89.99),
    ('AI202', 'Delhi (DEL)', 'Bangalore (BLR)', '2026-04-15 09:30:00', '2026-04-15 12:00:00', 150, 67, 119.99),
    ('6E303', 'Bangalore (BLR)', 'Hyderabad (HYD)', '2026-04-15 14:00:00', '2026-04-15 15:30:00', 120, 45, 59.99),
    ('SG404', 'Chennai (MAA)', 'Kolkata (CCU)', '2026-04-16 07:00:00', '2026-04-16 09:30:00', 160, 89, 104.99),
    ('AI505', 'Mumbai (BOM)', 'London (LHR)', '2026-04-16 22:00:00', '2026-04-17 05:30:00', 280, 112, 649.99),
    ('UK606', 'Delhi (DEL)', 'Dubai (DXB)', '2026-04-17 08:30:00', '2026-04-17 11:00:00', 200, 156, 299.99),
    ('AI707', 'Chennai (MAA)', 'Singapore (SIN)', '2026-04-17 23:00:00', '2026-04-18 06:30:00', 220, 98, 449.99),
    ('6E808', 'Hyderabad (HYD)', 'Mumbai (BOM)', '2026-04-18 10:00:00', '2026-04-18 11:45:00', 150, 34, 79.99),
    ('AI909', 'Bangalore (BLR)', 'San Francisco (SFO)', '2026-04-18 20:00:00', '2026-04-18 22:30:00', 300, 245, 899.99),
    ('UK010', 'Kolkata (CCU)', 'Bangkok (BKK)', '2026-04-19 12:00:00', '2026-04-19 16:30:00', 180, 67, 349.99),
    ('AI111', 'Delhi (DEL)', 'New York (JFK)', '2026-04-20 01:00:00', '2026-04-20 07:00:00', 350, 178, 1099.99),
    ('6E212', 'Mumbai (BOM)', 'Goa (GOI)', '2026-04-20 08:00:00', '2026-04-20 09:30:00', 120, 0, 49.99),
    ('SG313', 'Pune (PNQ)', 'Chennai (MAA)', '2026-04-21 15:00:00', '2026-04-21 17:15:00', 140, 42, 94.99),
    ('AI414', 'Ahmedabad (AMD)', 'Delhi (DEL)', '2026-04-22 07:30:00', '2026-04-22 09:30:00', 150, 18, 84.99),
    ('UK515', 'Kochi (COK)', 'Dubai (DXB)', '2026-04-22 20:30:00', '2026-04-22 23:15:00', 180, 95, 279.99);

-- Bookings with realistic PNRs (6-character alphanumeric)
INSERT INTO bookings (user_id, flight_id, pnr, seat_number, booking_status) VALUES
    (1, 1, 'XK9P2M', '14A', 'Confirmed'),
    (2, 2, 'R7HN4L', '7B', 'Confirmed'),
    (3, 5, 'T3V8QX', '22K', 'Checked-in'),
    (4, 3, 'W6JD9R', '8C', 'Confirmed'),
    (5, 6, 'M2FB5N', '15F', 'Confirmed'),
    (6, 7, 'Z9KL3P', '31A', 'Pending'),
    (7, 4, 'C4RS7H', '12D', 'Confirmed'),
    (8, 8, 'B8GN2V', '4E', 'Cancelled'),
    (9, 9, 'L5WX6T', '28B', 'Confirmed'),
    (10, 10, 'Q1YR4J', '9C', 'Checked-in'),
    (11, 11, 'N7HU3M', '45K', 'Confirmed'),
    (12, 12, 'F9PD8Z', '0', 'Cancelled'),
    (13, 13, 'K4SV2B', '11A', 'Confirmed'),
    (14, 14, 'G3TC6R', '6F', 'Confirmed'),
    (15, 15, 'H8WQ1L', '19D', 'Pending'),
    (2, 3, 'P5JM9X', '21C', 'Confirmed'),
    (4, 7, 'D6NK2F', '14G', 'Checked-in'),
    (6, 11, 'V2RB8Y', '52C', 'Confirmed'),
    (8, 1, 'J9XC4W', '18E', 'Cancelled'),
    (10, 2, 'S7TH3P', '3A', 'Confirmed');

-- Support tickets with realistic customer issues
INSERT INTO tickets (booking_id, issue_description, ticket_status, priority) VALUES
    (1, 'Special meal request - Jain vegetarian meal needed for passenger', 'Open', 'Medium'),
    (2, 'Unable to select seat online - website showing error on seat map', 'In Progress', 'High'),
    (3, 'Flight delayed by 4 hours - requesting compensation as per DGCA guidelines', 'Open', 'Urgent'),
    (4, 'Name correction needed - booking has "Singhania" but passport shows "Singh"', 'Open', 'Medium'),
    (5, 'Extra baggage allowance required for medical equipment', 'Resolved', 'Low'),
    (6, 'Payment deducted twice while booking - need refund for duplicate transaction', 'Open', 'Urgent'),
    (7, 'Wheelchair assistance requested at origin and destination airports', 'In Progress', 'High'),
    (9, 'Frequent flyer points not credited for last 3 flights', 'Resolved', 'Low'),
    (10, 'Infant booking issue - need to add 18-month-old to existing reservation', 'Open', 'Medium'),
    (13, 'Visa check failed for connecting flight - need itinerary for embassy', 'Open', 'High'),
    (15, 'Missed connection due to previous flight delay - need rebooking', 'In Progress', 'Urgent'),
    (16, 'Business class upgrade requested using reward points', 'Closed', 'Low'),
    (18, 'Boarding pass not generating for web check-in', 'Open', 'High'),
    (20, 'Lost baggage claim - AeroDesk reference: LHR123456', 'In Progress', 'Urgent');