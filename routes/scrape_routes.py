from flask import Blueprint, request, jsonify
from scrapers.google_maps import scrape_google_maps
from scrapers.indiamart import scrape_indiamart
from scrapers.justdial import scrape_justdial

scrape_bp = Blueprint('scrape', __name__)

@scrape_bp.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    source = data['source']
    keyword = data['keyword']
    location = data['location']

    if source == "google":
        result = scrape_google_maps(keyword, location)
    elif source == "indiamart":
        result = scrape_indiamart(keyword, location)
    elif source == "justdial":
        result = scrape_justdial(keyword, location)
    else:
        return jsonify({"error": "Invalid source"})

    return jsonify(result)