function togglePassword() {
    const passwordField = document.getElementById("password");

    if (passwordField.type === "password") {
        passwordField.type = "text";
    } else {
        passwordField.type = "password";
    }
}

// Simple client validation
document.getElementById("loginForm").addEventListener("submit", function(e) {

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    if (username.length < 3) {
        alert("Username must be at least 3 characters.");
        e.preventDefault();
    }

    if (password.length < 4) {
        alert("Password must be at least 4 characters.");
        e.preventDefault();
    }

});