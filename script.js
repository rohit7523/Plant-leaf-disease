document.addEventListener("DOMContentLoaded", function () {
    const tryBtn = document.getElementById("tryBtn");

    if (!tryBtn) {
        console.error("Try button not found!");
        return;
    }

    tryBtn.addEventListener("click", function () {
        window.open(
            "https://plant-leaf-disease-tuizvccj9ebebwujdffn5m.streamlit.app/",
            "_blank"
        );
    });
});
