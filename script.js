
document.addEventListener("DOMContentLoaded", () => {
    const tryBtn = document.getElementById("tryBtn");

    if (tryBtn) {
        tryBtn.addEventListener("click", () => {
            window.open(
                "https://plant-leaf-disease-tuizvccj9ebebwujdffn5m.streamlit.app/",
                "_blank"
            );
        });
    }
});
