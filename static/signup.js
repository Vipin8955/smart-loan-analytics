function togglePassword(id) {
    const field = document.getElementById(id);

    if (field.type === "password") {
        field.type = "text";
    } else {
        field.type = "password";
    }
}

document.getElementById("signupForm").addEventListener("submit", function(e) {

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (username.length < 3) {
        alert("Username must be at least 3 characters.");
        e.preventDefault();
        return;
    }

    if (password.length < 4) {
        alert("Password must be at least 4 characters.");
        e.preventDefault();
        return;
    }

    if (password !== confirmPassword) {
        alert("Passwords do not match.");
        e.preventDefault();
        return;
    }

});