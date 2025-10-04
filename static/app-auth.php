<?php
/**
 * H4K3R App Authentication System
 * 
 * This script ensures that the web content only works within the H4K3R Android app
 * and blocks access from normal browsers.
 * 
 * Usage: Include this at the top of any HTML/PHP file:
 * <?php include_once 'app-auth.php'; ?>
 * 
 * Features:
 * - Unique app signature verification
 * - Device fingerprinting
 * - Browser blocking
 * - Custom error pages
 * - Logging and monitoring
 */

session_start();

class H4K3RAppAuth {
    
    // Unique app secrets - Change these for security
    private const APP_SECRET_KEY = "H4K3R_TOOLS_2024_SECRET";
    private const APP_SIGNATURE = "H4K3R-ANDROID-APP";
    private const APP_VERSION = "2.0";
    
    // Expected headers from the Android app
    private const REQUIRED_HEADERS = [
        'X-H4K3R-App-Key',
        'X-H4K3R-Device-ID', 
        'X-H4K3R-App-Version',
        'X-H4K3R-Timestamp'
    ];
    
    public static function authenticate() {
        $auth = new self();
        return $auth->verifyAccess();
    }
    
    private function verifyAccess() {
        // DEBUG: Log all headers for debugging
        $this->logAccess("DEBUG: All headers: " . json_encode($this->getAllHeaders()));
        $this->logAccess("DEBUG: User agent: " . ($_SERVER['HTTP_USER_AGENT'] ?? 'none'));
        
        // Check if H4K3R app headers are present - this is the MAIN detection method
        if ($this->hasRequiredHeaders()) {
            $this->logAccess("DEBUG: H4K3R headers detected, verifying signature...");
            
            // Verify app signature
            if ($this->verifyAppSignature()) {
                $this->logAccess("DEBUG: Signature verified successfully");
                
                // Verify timestamp (prevent replay attacks)
                if ($this->verifyTimestamp()) {
                    $this->logAccess("SUCCESS: H4K3R App authenticated via headers");
                    return true;
                } else {
                    $this->blockAccess("Invalid timestamp");
                    return false;
                }
            } else {
                $this->logAccess("DEBUG: Signature verification failed");
            }
        }
        
        // FALLBACK: Allow H4K3R app user agent detection
        $userAgent = $_SERVER['HTTP_USER_AGENT'] ?? '';
        if (strpos($userAgent, 'H4K3R-Tools-Android') !== false) {
            $this->logAccess("SUCCESS: H4K3R App detected via User-Agent (fallback)");
            return true;
        }
        
        // Check if it's specifically the H4K3R app via X-REQUESTED-WITH header (Android WebView)
        $requestedWith = $_SERVER['HTTP_X_REQUESTED_WITH'] ?? '';
        if ($requestedWith === 'com.h4k3r.tool') {
            $this->logAccess("SUCCESS: H4K3R App detected via X-Requested-With header");
            return true;
        }
        
        // If no H4K3R app detection, check if it's a browser and block
        if ($this->isBrowser()) {
            $this->blockAccess("Browser access not allowed");
            return false;
        }
        
        // If we get here, it's not a browser but also not our app
        $this->blockAccess("Unrecognized client");
        return false;
    }
    
    private function hasRequiredHeaders() {
        foreach (self::REQUIRED_HEADERS as $header) {
            if (!isset($_SERVER['HTTP_' . str_replace('-', '_', strtoupper($header))])) {
                return false;
            }
        }
        return true;
    }
    
    private function verifyAppSignature() {
        $appKey = $_SERVER['HTTP_X_H4K3R_APP_KEY'] ?? '';
        $deviceId = $_SERVER['HTTP_X_H4K3R_DEVICE_ID'] ?? '';
        $timestamp = $_SERVER['HTTP_X_H4K3R_TIMESTAMP'] ?? '';
        
        // Generate expected signature
        $expectedSignature = hash_hmac('sha256', 
            self::APP_SIGNATURE . $deviceId . $timestamp, 
            self::APP_SECRET_KEY
        );
        
        return hash_equals($expectedSignature, $appKey);
    }
    
    private function verifyTimestamp() {
        $timestamp = intval($_SERVER['HTTP_X_H4K3R_TIMESTAMP'] ?? 0);
        $currentTime = time();
        
        // Allow 5 minutes window
        return abs($currentTime - $timestamp) < 300;
    }
    
    private function isBrowser() {
        $userAgent = $_SERVER['HTTP_USER_AGENT'] ?? '';
        $requestedWith = $_SERVER['HTTP_X_REQUESTED_WITH'] ?? '';
        
        // If it has H4K3R signatures, it's our app, not a browser
        if (strpos($userAgent, 'H4K3R-Tools-Android') !== false) {
            return false;
        }
        
        // If X-Requested-With header indicates our app, it's not a browser
        if ($requestedWith === 'com.h4k3r.tool') {
            return false;
        }
        
        // If it has H4K3R authentication headers, it's our app
        if ($this->hasRequiredHeaders()) {
            return false;
        }
        
        // Check for desktop browsers (more specific patterns)
        $desktopBrowserPatterns = [
            '/Chrome\/.*(?!.*Mobile)/i', // Desktop Chrome (not mobile)
            '/Firefox\/.*(?!.*Mobile)/i', // Desktop Firefox
            '/Safari\/.*(?!.*Mobile)/i', // Desktop Safari
            '/Edge\//i',
            '/Opera\//i'
        ];
        
        foreach ($desktopBrowserPatterns as $pattern) {
            if (preg_match($pattern, $userAgent)) {
                return true;
            }
        }
        
        // Check if it's a mobile browser without app context
        if (empty($requestedWith) && (
            strpos($userAgent, 'Chrome/') !== false ||
            strpos($userAgent, 'Firefox/') !== false ||
            strpos($userAgent, 'Safari/') !== false
        )) {
            // If it's mobile but no X-Requested-With, likely a mobile browser
            return true;
        }
        
        return false;
    }
    
    private function blockAccess($reason) {
        // Log the blocked attempt
        $this->logAccess("BLOCKED: " . $reason);
        
        // Send 403 Forbidden status
        http_response_code(403);
        
        // Show custom block page
        $this->showBlockPage($reason);
        exit();
    }
    
    private function showBlockPage($reason) {
        ?>
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Denied - H4K3R Tools</title>
            <style>
                body {
                    font-family: 'Courier New', monospace;
                    background: linear-gradient(135deg, #0a0a0a, #1a1a2e);
                    color: #00ff41;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    text-align: center;
                }
                .container {
                    background: rgba(0, 0, 0, 0.8);
                    border: 2px solid #00ff41;
                    border-radius: 10px;
                    padding: 40px;
                    max-width: 500px;
                    box-shadow: 0 0 30px #00ff41;
                }
                h1 {
                    color: #ff0040;
                    font-size: 2.5em;
                    margin-bottom: 20px;
                    text-shadow: 0 0 10px #ff0040;
                }
                .skull {
                    font-size: 4em;
                    margin: 20px 0;
                }
                .reason {
                    background: rgba(255, 0, 64, 0.1);
                    border: 1px solid #ff0040;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 5px;
                }
                .blink {
                    animation: blink 1s linear infinite;
                }
                @keyframes blink {
                    0%, 50% { opacity: 1; }
                    51%, 100% { opacity: 0; }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="skull">💀</div>
                <h1 class="blink">ACCESS DENIED</h1>
                <p>This content is only accessible through the <strong>H4K3R Tools Android App</strong></p>
                <div class="reason">
                    <strong>Reason:</strong> <?php echo htmlspecialchars($reason); ?>
                </div>
                <p>Please download and use the official H4K3R Tools app.</p>
                <p><small>Incident ID: <?php echo uniqid(); ?></small></p>
            </div>
        </body>
        </html>
        <?php
    }
    
    private function logAccess($status) {
        $logFile = __DIR__ . '/logs/app-auth.log';
        
        // Create logs directory if it doesn't exist
        $logDir = dirname($logFile);
        if (!is_dir($logDir)) {
            mkdir($logDir, 0755, true);
        }
        
        $logData = [
            'timestamp' => date('Y-m-d H:i:s'),
            'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown',
            'device_id' => $_SERVER['HTTP_X_H4K3R_DEVICE_ID'] ?? 'none',
            'status' => $status,
            'url' => $_SERVER['REQUEST_URI'] ?? 'unknown'
        ];
        
        $logLine = json_encode($logData) . "\n";
        file_put_contents($logFile, $logLine, FILE_APPEND | LOCK_EX);
    }
    
    // Helper method to get device information
    public static function getDeviceInfo() {
        return [
            'device_id' => $_SERVER['HTTP_X_H4K3R_DEVICE_ID'] ?? 'unknown',
            'app_version' => $_SERVER['HTTP_X_H4K3R_APP_VERSION'] ?? 'unknown',
            'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
            'timestamp' => date('Y-m-d H:i:s')
        ];
    }
    
    // Helper method to get all HTTP headers for debugging
    private function getAllHeaders() {
        $headers = [];
        foreach ($_SERVER as $key => $value) {
            if (strpos($key, 'HTTP_') === 0) {
                $headerName = str_replace('HTTP_', '', $key);
                $headerName = str_replace('_', '-', $headerName);
                $headers[$headerName] = $value;
            }
        }
        return $headers;
    }
}

// Auto-authenticate when this file is included
if (!H4K3RAppAuth::authenticate()) {
    // Authentication failed, script will exit in blockAccess method
}

// If we reach here, authentication was successful
$_SESSION['h4k3r_authenticated'] = true;
$_SESSION['h4k3r_device_info'] = H4K3RAppAuth::getDeviceInfo();

?>
