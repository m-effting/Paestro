def apply_classification_rules(attendance_data):
    """Aplica regras de classificação para determinar o status de faltas dos alunos.
    
    Regras para ensino não obrigatório (GT0-GT3):
    - Monitorar Faltas: 10+ faltas em um mês OU presença < 40%
    - Faltoso: 12+ faltas em um mês OU presença < 30%
    
    Regras para ensino obrigatório (GT4-9º):
    - Monitorar Faltas: 7+ faltas em um mês OU presença < 40%
    - Faltoso: 10+ faltas em um mês OU presença < 30%
    
    Regras para faltas justificadas (ambos os tipos de ensino):
    - Monitorar FJs: 45%+ das presenças totais são FJs
    - Muitas FJs: 60%+ das presenças totais são FJs
    

    Apply classification rules to determine student status based on attendance data.
    
    Args:
        attendance_data (dict): The parsed attendance data
        
    Returns:
        list: Students with their classification statuses
    """
    classified_students = []
    
    # Define education levels
    # Ensino não obrigatório (infantil até GT3)
    non_compulsory = ['GT0', 'GT1', 'GT2', 'GT3']
    # Ensino obrigatório (infantil GT4, GT5 e fundamental 1º ao 9º ano)
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
        
        # Limiar para considerar poucos dias de estudo (todos os totais baixos)
        # Se o aluno tem poucos registros totais, considerar como regular
        total_records = total_present + total_absences + total_justified
        if total_records < 5:  # Se tem menos de 5 registros no total
            statuses.append("Regular")
            # Update student with status and skip further processing
            student_result = student.copy()
            student_result['status'] = statuses
            student_result['situacao'] = statuses  # Mantém 'situacao' para compatibilidade
            
            # Garantir que o campo escola esteja preenchido
            if 'escola' not in student_result and 'unidade' in student_result:
                student_result['escola'] = student_result['unidade']
            elif 'escola' not in student_result:
                student_result['escola'] = "Escola não identificada"
                
            classified_students.append(student_result)
            continue  # Pula para o próximo aluno
        
        # Determine if education is compulsory based on class name
        education_type = None
        
        # Primeiro verificamos por GT0, GT1, GT2, GT3 (ensino não obrigatório)
        # Verificação mais completa para detectar GT3 em diferentes formatos (GT3A, GT 3 A, etc)
        if 'GT3' in class_name or 'GT 3' in class_name or any(class_name.startswith(prefix) for prefix in non_compulsory):
            education_type = 'non_compulsory'
        
        # Se não for não obrigatório, verifica se é obrigatório (GT4, GT5, 1º-9º)
        if not education_type:
            for prefix in compulsory:
                if class_name.startswith(prefix):
                    education_type = 'compulsory'
                    break
        
        # Verificação adicional para padrões de turma diretos do direct_parser
        if not education_type and 'education_type' in student:
            parser_type = student.get('education_type', '').lower()
            if parser_type == 'obrigatorio' or parser_type == 'fundamental' or parser_type == 'infantil_obrigatorio':
                education_type = 'compulsory'
            elif parser_type == 'nao_obrigatorio' or parser_type == 'infantil':
                education_type = 'non_compulsory'
        
        # Default to compulsory if we can't determine
        if not education_type:
            education_type = 'compulsory'
        
        # Rules implementation
        
        # 1. Check if student is an Absentee (Faltoso)
        is_absentee = False
        
        # Monthly absence threshold for absentee (Faltoso)
        # Não obrigatório (GT0-GT3): 12+ faltas/mês
        # Obrigatório (GT4-9º): 10+ faltas/mês
        monthly_threshold = 12 if education_type == 'non_compulsory' else 10
        
        # Verificar cada mês separadamente para faltas acumuladas
        for month, count in monthly_absences.items():
            # Converter month para int se for string numérica
            month_key = int(month) if isinstance(month, str) and month.isdigit() else month
            # Extrair o valor numérico se for um objeto ou dicionário
            month_count = count if isinstance(count, (int, float)) else 0
            
            if month_count >= monthly_threshold:
                is_absentee = True
                break
        
        # Attendance percentage threshold for absentee (menos de 30% de presença)
        if total_records > 0 and attendance_percentage < 30:
            is_absentee = True
            
        if is_absentee:
            statuses.append("Faltoso")
        
        # 2. Check if student needs absence monitoring (if not already an absentee)
        if "Faltoso" not in statuses:
            monitor_absences = False
            
            # Monthly absence threshold for monitoring (Monitorar Faltas)
            # Não obrigatório (GT0-GT3): 10+ faltas/mês
            # Obrigatório (GT4-9º): 7+ faltas/mês
            monitor_threshold = 10 if education_type == 'non_compulsory' else 7
            
            # Verificar cada mês separadamente para faltas que exigem monitoramento
            for month, count in monthly_absences.items():
                # Converter month para int se for string numérica
                month_key = int(month) if isinstance(month, str) and month.isdigit() else month
                # Extrair o valor numérico se for um objeto ou dicionário
                month_count = count if isinstance(count, (int, float)) else 0
                
                if month_count >= monitor_threshold:
                    monitor_absences = True
                    break
            
            # Attendance percentage threshold for monitoring (menos de 40% de presença)
            if total_records > 0 and attendance_percentage < 40:
                monitor_absences = True
                
            if monitor_absences:
                statuses.append("Monitorar Faltas")
        
        # 3. Check for justified absence monitoring (igual para ambos os ensinos)
        if total_records > 0 and total_justified > 0:
            # Calcular a porcentagem de faltas justificadas sobre o total de presenças
            justified_percentage = (total_justified / total_records) * 100
            
            # Verificar se tem muitas faltas justificadas (60%+ das presenças totais são FJs)
            if justified_percentage >= 60:
                statuses.append("Muitas FJs")
            # Verificar se precisamos monitorar faltas justificadas (45%+ das presenças totais são FJs)
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
