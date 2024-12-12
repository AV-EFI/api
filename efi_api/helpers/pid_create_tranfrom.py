def wrap_pid_data(data: dict) -> list:
    """
    Common function to wrap PID data in required format
    
    Args:
        data: Input object to be wrapped
        
    Returns:
        list: Wrapped data in required format
    """
    return [
        {
            "type": "KIP",
            "parsed_data": "http://typeapi.lab.pidconsortium.net/v1/types/schema/21.T11969/873d5c9f6ebbffecf1df",
            "idx": 1
        },
        {
            "type": "has_record", 
            "parsed_data": data,
            "idx": 2
        }
    ]