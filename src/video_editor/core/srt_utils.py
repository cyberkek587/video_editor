import pysrt

def parse_srt(file_path):
    """
    Parses an SRT file and returns a list of dictionaries with 'start', 'end', and 'text'.
    Time is in seconds.
    """
    subs = pysrt.open(file_path)
    parsed_subs = []
    for sub in subs:
        parsed_subs.append({
            'start': sub.start.ordinal / 1000.0,
            'end': sub.end.ordinal / 1000.0,
            'text': sub.text.replace('\n', ' ')
        })
    return parsed_subs
