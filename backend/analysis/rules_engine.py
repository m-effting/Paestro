def apply_classification_rules(attendance_data):
    """
    Apply classification rules to determine student status based on attendance data.
    
    Args:
        attendance_data (dict): The parsed attendance data
        
    Returns:
        list: Students with their classification statuses
    """
    classified_students = []
    
    # Define education levels
    non_compulsory = ['GT0', 'GT1', 'GT2', 'GT3']
    compulsory = ['GT4', 'GT5'] + [f"{i}º" for i in range(1, 10)]  # GT4, GT5, 1º to 9º
    
    # Check each student
    for student in attendance_data.get('students', []):
        # Initialize status list
        statuses = []
        
        # Extract student data
        attendance_percentage = student.get('percentual_presenca', 0)
        total_present = student.get('P', 0)
        total_absences = student.get('F', 0)
        total_justified = student.get('FJ', 0)
        monthly_absences = student.get('faltas_por_mes', {})
        class_name = student.get('turma', '').upper()
        
        # Determine if education is compulsory
        education_type = None
        for prefix in non_compulsory:
            if class_name.startswith(prefix):
                education_type = 'non_compulsory'
                break
        
        if not education_type:
            for prefix in compulsory:
                if class_name.startswith(prefix):
                    education_type = 'compulsory'
                    break
        
        # Default to compulsory if we can't determine
        if not education_type:
            education_type = 'compulsory'
        
        # Calculate total records
        total_records = total_present + total_absences + total_justified
        
        # Rules implementation
        
        # 1. Check if student is an Absentee (Faltoso)
        is_absentee = False
        
        # Monthly absence threshold for absentee
        monthly_threshold = 13 if education_type == 'non_compulsory' else 10
        for month, count in monthly_absences.items():
            if count >= monthly_threshold:
                is_absentee = True
                break
        
        # Attendance percentage threshold for absentee
        if total_records > 0 and attendance_percentage <= 20:
            is_absentee = True
            
        if is_absentee:
            statuses.append("Faltoso")
        
        # 2. Check if student needs absence monitoring (if not already an absentee)
        if "Faltoso" not in statuses:
            monitor_absences = False
            
            # Monthly absence threshold for monitoring
            monitor_threshold = 10 if education_type == 'non_compulsory' else 7
            for month, count in monthly_absences.items():
                if count >= monitor_threshold:
                    monitor_absences = True
                    break
            
            # Attendance percentage threshold for monitoring
            if total_records > 0 and attendance_percentage <= 35:
                monitor_absences = True
                
            if monitor_absences:
                statuses.append("Monitorar Faltas")
        
        # 3. Check for justified absence monitoring
        if total_records > 0:
            justified_percentage = (total_justified / total_records) * 100
            
            if justified_percentage >= 60:
                statuses.append("Muitas FJs")
            elif justified_percentage >= 45:
                statuses.append("Monitorar FJs")
        
        # Add default status if none assigned
        if not statuses:
            statuses.append("Regular")
        
        # Update student with status
        student_result = student.copy()
        student_result['status'] = statuses
        student_result['situacao'] = statuses  # Mantém 'situacao' para compatibilidade
        
        # Garantir que o campo escola esteja preenchido (usando unidade se estiver disponível)
        if 'escola' not in student_result and 'unidade' in student_result:
            student_result['escola'] = student_result['unidade']
        elif 'escola' not in student_result:
            student_result['escola'] = "Escola não identificada"
            
        classified_students.append(student_result)
    
    return classified_students
