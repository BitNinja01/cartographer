"""Entry point for: python -m cartographer.tagger "Course Name" """
import sys
from cartographer.tagger.server import run_tagger

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m cartographer.tagger \"Course Name\"")
        sys.exit(1)
    course_name = " ".join(sys.argv[1:])
    run_tagger(course_name)
