function jQuery(target) {
  const element =
    typeof target === "string" ? document.querySelector(target) : target;

  if (!element) throw new Error("Element not found");

  const api = {
    [0]: element,
    click(fn) {
      if (fn === undefined) {
        element.click();
      } else {
        api.on("click", fn);
      }

      return api;
    },
    text(text) {
      if (text === undefined) {
        return element.textContent;
      }

      element.textContent = text;
      return api;
    },
    on(eventName, fn) {
      element.addEventListener(eventName, fn);
      return api;
    },
    attr(name, value) {
      if (value === undefined) {
        return element.getAttribute(name);
      }

      element.setAttribute(name, value);
      return api;
    },
    addClass(className) {
      element.classList.add(className);
      return api;
    },
    removeClass(className) {
      element.classList.remove(className);
      return api;
    },
  };

  return api;
}

export { jQuery as $ };
