from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import os
import uuid
from datetime import datetime
from models.face_matcher import AdvancedFaceMatcher
from utils.helpers import save_person_to_db, save_uploaded_file, load_persons_from_db
import logging

logger = logging.getLogger(__name__)

person_bp = Blueprint('person', __name__, url_prefix='/person')

# MANUAL WORK: You need to initialize this in app.py and pass the config
face_matcher = None
config = None

def init_person_routes(app_config, face_matcher_instance):
    global config, face_matcher
    config = app_config
    face_matcher = face_matcher_instance

@person_bp.route('/upload', methods=['GET'])
def upload_person_form():
    """Display person upload form"""
    return render_template('upload_person.html')

@person_bp.route('/upload', methods=['POST'])
def upload_person():
    """Handle person details upload"""
    try:
        # Extract form data
        person_data = {
            'name': request.form.get('name', '').strip(),
            'age': request.form.get('age', '').strip(),
            'last_seen_location': request.form.get('last_seen_location', '').strip(),
            'last_seen_time': request.form.get('last_seen_time', '').strip(),
            'description': request.form.get('description', '').strip(),
            'contact_info': request.form.get('contact_info', '').strip(),
            'additional_notes': request.form.get('additional_notes', '').strip()
        }
        
        # Validate required fields
        if not person_data['name']:
            return jsonify({'success': False, 'error': 'Name is required'}), 400
        
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'Image is required'}), 400
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'success': False, 'error': 'No image selected'}), 400
        
        # Save uploaded image
        image_path, error = save_uploaded_file(
            image_file, 
            config.UPLOAD_FOLDER, 
            'persons'
        )
        
        if error:
            return jsonify({'success': False, 'error': f'File upload failed: {error}'}), 400
        
        person_data['image_path'] = image_path
        
        # Extract face embeddings
        logger.info(f"Extracting embeddings for {person_data['name']}")
        embedding = face_matcher.extract_embeddings(image_path)
        
        if embedding is None:
            # Clean up uploaded image
            try:
                os.remove(image_path)
            except:
                pass
            return jsonify({'success': False, 'error': 'Could not detect a face in the image. Please upload a clearer image with a visible face.'}), 400
        
        # Validate face quality
        is_quality_ok, quality_message = face_matcher.validate_face_quality(embedding)
        if not is_quality_ok:
            try:
                os.remove(image_path)
            except:
                pass
            return jsonify({'success': False, 'error': f'Face quality issue: {quality_message}'}), 400
        
        person_data['embedding'] = embedding
        
        # Save to database
        person_id = save_person_to_db(person_data, config.PERSONS_DB_FILE)
        
        if person_id:
            logger.info(f"Successfully registered person: {person_data['name']} with ID: {person_id}")
            return jsonify({
                'success': True,
                'person_id': person_id,
                'message': f'Person {person_data["name"]} registered successfully and is now being monitored'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save person data'}), 500
            
    except Exception as e:
        logger.error(f"Error in person upload: {e}")
        return jsonify({'success': False, 'error': f'Internal server error: {str(e)}'}), 500

@person_bp.route('/list')
def list_persons():
    """Display list of all registered persons"""
    try:
        # Check if config has the required attribute
        if not hasattr(config, 'PERSONS_DB_FILE'):
            return render_template('person_list.html', persons={})
        
        persons = load_persons_from_db(config.PERSONS_DB_FILE)
        return render_template('person_list.html', persons=persons)
    except Exception as e:
        logger.error(f"Error loading persons list: {e}")
        return render_template('person_list.html', persons={})