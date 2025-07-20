#!/usr/bin/env python3
"""Batch processor for multiple Endesa accounts."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from endesa import EndesaClient
from config import read_credentials


def process_account(credential_file: str) -> str:
    """Process a single account from a credential file."""
    try:
        # Read credentials
        creds = read_credentials(credential_file)
        if not creds:
            return f"ERROR: {credential_file} - Invalid credentials"
        
        email, password = creds
        
        # Create client
        client = EndesaClient(email, password)
        
        try:
            # Login and retrieve data
            client.login()
            account_info = client.get_account_info()
            
            # Format result
            result = f"IBAN: {account_info['iban']} Phone: {account_info['phone']}"
            return f"SUCCESS: {credential_file} - {result}"
            
        except Exception as e:
            return f"ERROR: {credential_file} - {str(e)}"
        finally:
            client.close()
            
    except Exception as e:
        return f"ERROR: {credential_file} - {str(e)}"


def process_credentials_directory(credentials_dir: str, max_workers: int = 50, output_file: str = "results.txt"):
    """Process all credential files in a directory concurrently."""
    # Get credential files
    credential_files = []
    for filename in os.listdir(credentials_dir):
        if filename.endswith('.txt'):
            credential_files.append(os.path.join(credentials_dir, filename))
    
    if not credential_files:
        print(f"No credential files found in {credentials_dir}")
        return
    
    print(f"Processing {len(credential_files)} files with {max_workers} workers...")
    
    # Clear output file
    with open(output_file, "w") as f:
        pass
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    # Process with ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(process_account, file): file for file in credential_files}
        
        # Process results
        for future in as_completed(futures):
            try:
                result = future.result()
                success = result.startswith("SUCCESS")
                
                # Write result
                with open(output_file, "a") as f:
                    f.write(result + "\n")
                
                # Update counters
                if success:
                    successful += 1
                else:
                    failed += 1
                
                # Progress update
                total = successful + failed
                if total % 10 == 0:
                    print(f"Processed: {total}/{len(credential_files)}")
                
            except Exception as e:
                failed += 1
                with open(output_file, "a") as f:
                    f.write(f"ERROR: {futures[future]} - {str(e)}\n")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Final statistics
    print(f"Completed: {successful} successful, {failed} failed")
    print(f"Time: {total_time:.1f}s, Rate: {len(credential_files)/total_time:.1f} req/s")


def main():
    """Main function to process credentials directory."""
    # Process credentials directory
    if os.path.exists("credentials"):
        process_credentials_directory("credentials", max_workers=50)
    else:
        print("Create 'credentials' directory with .txt files (email:password format)")


if __name__ == "__main__":
    main() 