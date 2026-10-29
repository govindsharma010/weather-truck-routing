import { useEffect, useId, useRef, useState } from "react";
import { searchPlaces } from "../lib/api.js";

/**
 * Typeahead for a place. `value` is `{label, lat, lon}` once a suggestion is picked; until then the
 * parent receives the raw text (`{label}` only) and the server geocodes it to the top match.
 */
export default function LocationInput({ label, value, onChange, placeholder }) {
  const [text, setText] = useState(value?.label ?? "");
  const [options, setOptions] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();
  const abortRef = useRef(null);

  useEffect(() => {
    if (!open || text.trim().length < 3 || value?.lat !== undefined) return;
    const timer = setTimeout(() => {
      abortRef.current?.abort();
      const ctl = new AbortController();
      abortRef.current = ctl;
      searchPlaces(text, ctl.signal)
        .then((r) => {
          setOptions(r);
          setActive(-1);
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(timer);
  }, [text, open, value?.lat]);

  const pick = (opt) => {
    setText(opt.label);
    setOptions([]);
    setOpen(false);
    onChange(opt);
  };

  const onKeyDown = (e) => {
    if (!options.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => (a + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => (a <= 0 ? options.length - 1 : a - 1));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      pick(options[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <label className="field">
      <span>{label}</span>
      <div className="combo">
        <input
          type="text"
          value={text}
          placeholder={placeholder}
          autoComplete="off"
          role="combobox"
          aria-expanded={open && options.length > 0}
          aria-controls={listId}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
            onChange({ label: e.target.value }); // typed but not yet resolved
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={onKeyDown}
          required
        />
        {open && options.length > 0 && (
          <ul id={listId} className="suggestions" role="listbox">
            {options.map((o, i) => (
              <li
                key={`${o.lat},${o.lon}`}
                role="option"
                aria-selected={i === active}
                className={i === active ? "active" : ""}
                onMouseDown={() => pick(o)}
              >
                {o.label}
              </li>
            ))}
          </ul>
        )}
      </div>
    </label>
  );
}