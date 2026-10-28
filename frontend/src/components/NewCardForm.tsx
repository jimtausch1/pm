import { useState, type SubmitEvent } from "react";

const initialFormState = { title: "", details: "" };

type NewCardFormProps = {
  onAdd: (title: string, details: string) => void;
};

export const NewCardForm = ({ onAdd }: NewCardFormProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [formState, setFormState] = useState(initialFormState);

  const handleSubmit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.title.trim()) {
      return;
    }
    onAdd(formState.title.trim(), formState.details.trim());
    setFormState(initialFormState);
    setIsOpen(false);
  };

  return (
    <div className="mt-4">
      {isOpen ? (
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            value={formState.title}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, title: event.target.value }))
            }
            placeholder="Card title"
            className="w-full rounded-xl border border-(--stroke) bg-white px-3 py-2 text-sm font-medium text-foreground outline-none transition focus:border-(--primary-blue)"
            required
          />
          <textarea
            value={formState.details}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, details: event.target.value }))
            }
            placeholder="Details"
            rows={3}
            className="w-full resize-none rounded-xl border border-(--stroke) bg-white px-3 py-2 text-sm text-(--gray-text) outline-none transition focus:border-(--primary-blue)"
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="rounded-full bg-(--secondary-purple) px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Add card
            </button>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setFormState(initialFormState);
              }}
              className="rounded-full border border-(--stroke) px-3 py-2 text-xs font-semibold uppercase tracking-wide text-(--gray-text) transition hover:text-foreground"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="w-full rounded-full border border-dashed border-(--stroke) px-3 py-2 text-xs font-semibold uppercase tracking-wide text-(--primary-blue) transition hover:border-(--primary-blue)"
        >
          Add a card
        </button>
      )}
    </div>
  );
};
