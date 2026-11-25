"""Fictional dispatch service used only by the bundled example."""


def enqueue(queue, request):
    if request not in queue:
        queue.append(request)
    return len(queue)


def display_label(raw):
    value = raw.strip()
    if not value:
        raise ValueError("Empty label")
    return value
