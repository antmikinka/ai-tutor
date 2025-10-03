"""
Minimal AI Math Tutor Backend Server
Fallback server for when full dependencies are not available
"""

import json
import sys
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socketserver
import threading

class MinimalMathHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for basic math tutor functionality"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == '/health':
            self.send_health_response()
        elif path == '/':
            self.send_info_response()
        elif path.startswith('/api/math/'):
            self.handle_math_request(parsed_path)
        else:
            self.send_404()

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == '/api/math/solve':
            self.handle_math_solve()
        else:
            self.send_404()

    def send_health_response(self):
        """Send health check response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0-minimal',
            'services': {
                'ai_service': False,
                'audio_service': False,
                'model_service': False
            },
            'mode': 'minimal'
        }

        self.wfile.write(json.dumps(response).encode())

    def send_info_response(self):
        """Send server information response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        response = {
            'name': 'AI Math Tutor Backend (Minimal)',
            'version': '1.0.0-minimal',
            'description': 'Minimal backend server for basic functionality',
            'endpoints': {
                'health': '/health',
                'math_basic': '/api/math/basic',
                'math_solve': '/api/math/solve'
            },
            'limitations': [
                'No AI model support',
                'Basic math calculations only',
                'No voice interaction',
                'No drawing analysis'
            ]
        }

        self.wfile.write(json.dumps(response).encode())

    def handle_math_request(self, parsed_path):
        """Handle basic math requests"""
        try:
            # Extract problem from query parameters
            query_params = urllib.parse.parse_qs(parsed_path.query)
            problem = query_params.get('problem', [''])[0]

            if not problem:
                self.send_400('Problem parameter required')
                return

            # Simple math evaluation (basic safety check)
            if any(word in problem.lower() for word in ['import', 'exec', 'eval', 'open', 'file']):
                self.send_400('Invalid mathematical expression')
                return

            try:
                # Basic math calculation
                result = self.safe_eval(problem)
                response = {
                    'success': True,
                    'problem': problem,
                    'result': str(result),
                    'explanation': f'Basic calculation: {problem} = {result}',
                    'steps': [
                        f'Input: {problem}',
                        f'Result: {result}'
                    ],
                    'timestamp': datetime.utcnow().isoformat(),
                    'mode': 'minimal'
                }

                self.send_json_response(response)

            except Exception as e:
                response = {
                    'success': False,
                    'error': f'Cannot evaluate expression: {str(e)}',
                    'timestamp': datetime.utcnow().isoformat(),
                    'mode': 'minimal'
                }

                self.send_json_response(response, status_code=400)

        except Exception as e:
            self.send_500(f'Internal server error: {str(e)}')

    def handle_math_solve(self):
        """Handle POST math solving requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
                problem = data.get('problem', '')

                if not problem:
                    self.send_400('Problem field required')
                    return

                # Simple math evaluation
                result = self.safe_eval(problem)

                response = {
                    'success': True,
                    'problem': problem,
                    'solution': {
                        'result': str(result),
                        'explanation': f'Calculated: {problem} = {result}',
                        'steps': [
                            f'Given: {problem}',
                            f'Solution: {result}'
                        ]
                    },
                    'confidence': 0.9,
                    'timestamp': datetime.utcnow().isoformat(),
                    'mode': 'minimal'
                }

                self.send_json_response(response)

            except json.JSONDecodeError:
                self.send_400('Invalid JSON data')

        except Exception as e:
            self.send_500(f'Internal server error: {str(e)}')

    def safe_eval(self, expression):
        """Safely evaluate mathematical expressions"""
        # Only allow basic math operations
        allowed_chars = set('0123456789+-*/().^% ')
        allowed_words = {'sin', 'cos', 'tan', 'log', 'sqrt', 'abs', 'pi', 'e'}

        # Check for forbidden characters
        if not all(c in allowed_chars or c.isalpha() for c in expression):
            raise ValueError("Invalid characters in expression")

        # Check for forbidden words
        words = ''.join(c if c.isalpha() else ' ' for c in expression).split()
        for word in words:
            if word.lower() not in allowed_words:
                raise ValueError(f"Invalid word in expression: {word}")

        # Simple evaluation (this is a basic implementation)
        # In production, use a proper math expression evaluator
        try:
            # Replace common math functions
            expr = expression.replace('^', '**')
            expr = expr.replace('pi', str(3.14159265359))
            expr = expr.replace('e', str(2.71828182846))

            # For demonstration, we'll use a very limited eval
            # WARNING: In production, use a proper math parser!
            if any(func in expr.lower() for func in ['sin', 'cos', 'tan', 'log', 'sqrt']):
                # For trigonometric functions, return a placeholder
                return f"[Math function result for: {expression}]"

            result = eval(expr, {'__builtins__': {}}, {})
            return result

        except:
            raise ValueError("Cannot evaluate expression")

    def send_json_response(self, data, status_code=200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        self.wfile.write(json.dumps(data).encode())

    def send_400(self, message):
        """Send 400 Bad Request response"""
        response = {
            'error': message,
            'timestamp': datetime.utcnow().isoformat(),
            'mode': 'minimal'
        }
        self.send_json_response(response, 400)

    def send_404(self):
        """Send 404 Not Found response"""
        response = {
            'error': 'Endpoint not found',
            'timestamp': datetime.utcnow().isoformat(),
            'mode': 'minimal'
        }
        self.send_json_response(response, 404)

    def send_500(self, message):
        """Send 500 Internal Server Error response"""
        response = {
            'error': message,
            'timestamp': datetime.utcnow().isoformat(),
            'mode': 'minimal'
        }
        self.send_json_response(response, 500)

    def log_message(self, format, *args):
        """Custom log message format"""
        print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {format % args}')

def run_minimal_server(host='localhost', port=8000):
    """Run the minimal server"""
    server_address = (host, port)
    httpd = HTTPServer(server_address, MinimalMathHandler)

    print(f"Minimal AI Math Tutor Server starting...")
    print(f"Server running at http://{host}:{port}")
    print(f"Health check: http://{host}:{port}/health")
    print(f"API documentation: http://{host}:{port}/")
    print("")
    print("Available endpoints:")
    print("  GET  /health        - Health check")
    print("  GET  /              - Server information")
    print("  GET  /api/math/basic?problem=X - Basic math calculation")
    print("  POST /api/math/solve - Solve math problem")
    print("")
    print("LIMITATIONS: This is a minimal server without AI capabilities")
    print("Only basic mathematical calculations are supported")
    print("")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Minimal AI Math Tutor Server')
    parser.add_argument('--host', default='localhost', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')

    args = parser.parse_args()

    run_minimal_server(args.host, args.port)