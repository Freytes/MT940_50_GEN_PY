#! python3
#-------------------------------------------------------------------------------
# Name:        Swift MT940/950 Generator
# Purpose:     Takes a specific csv file and converts it to
#              either an MT940 or MT950 swift message.
# Version:     1.1.0
# Author:      Thomas Edward Rudge
# Created:     25-10-2015
# Copyright:   (c) Thomas Edward Rudge 2015
# Licence:     GPL
#-------------------------------------------------------------------------------
# Written for Python 3 (3.3)

import csv, datetime


def gen_mt9(active_file, msg_type, target_file, dtf='DDMMYYYY',
            appid='A', servid='21', session_no='0000', seqno='000000', ## Basic Header Block
            drctn='I', msg_prty='N', dlvt_mnty='', obs='', inp_time='0000', ## Application Header Block
            out_date='010101', out_time='1200', mir=True, ## Application Header Block
            f113=False, mur='MT940950GEN', ## User Header Block
            chk=False
            ):
    '''
    CSV --> MT940/50

    All arguments must be strings.
    ---------------------------------------------------------------
    active_file : The location of the csv file to be read.
    msg_type    : Either 940 or 950
    target_file : The location where the MT940/50 should be written
    ---------------------------------------------------------------

    ## Optional Arguments
    dtf         : The format of the dates present in the csv file - YYYYMMDD
                                                                    DDMMYYYY (Default)
                                                                    MMDDYYYY
    {1: Basic Header Block ----------------------------------------
    appid       : Application ID - A = General Purpose Application
                                   F = Financial Application
                                   L = Logins
    servid      : Service ID - 01 = FIN/GPA
                               21 = ACK/NAK
    session_no  : Session Number
    seqno       : Sequence Number
    {2: Application Header Block ----------------------------------
    drctn       : Direction - I =Input (to swift)
                              O = Output (from swift)
    msg_prty    : Message Priority - S = System
                                     N = Normal
                                     U = Urgent)
    dlvt_mnty   : Delivery Monitoring Field - 1 = Non delivery warning
                  [Input Only]                2 = Delivery notification
                                              3 = Both (1 & 2)
    obs         : Obsolescence period - 003 = 15 minutes (When priority = U)
                  [Input Only]          020 = 100 minutes (When priority = N)
    inp_time    : Input Time of Sender - HHMM - [Output Only]
    out_time    : Output Time from Swift - HHMM - [Output Only]
    out_date    : Output Date from Swift - YYMMDD - [Output Only]
    mir         : Message Input Reference - If True MIR is autogenerated, all
                  [Output Only]             other values will be used as the MIR
    {3: User Header Block -----------------------------------------
    f113        : Banking Priority Code - nnnn
    mur         : Message User Reference
    {5: Trailer Block ---------------------------------------------
    chk         : The checksum for the message.
    '''

    with open(active_file,'r') as afile, open(target_file, 'a') as zfile:
        ## Keep track of the last lines details, so that we know when to close the statement or message.
        prev_line = {
            'account': '',
            'sendbic': '',
            'recvbic': '',
            'stmtno': '',
            'stmtpg': '',
            'ccy': '',
            'cbalsgn': '',
            'cbaltyp': '',
            'cbaldte': '',
            'cbal': '',
            'abalsgn': '',
            'abaldte': '',
            'abal': ''
            }
        csv_file = csv.reader(afile)
        trn = 0 ## Used to numerate TRNs if none present in file.
        lst_line = None
        for line in csv_file:
            zline = '' ## Line that will be written to the MT9 file.
            ## Ignore the header
            if line and line[-2].upper().replace(' ', '') == 'REF4(MT940ONLY)' or line[0] == '':
                continue
            ## Invalid column count should raise an error.
            elif len(line) != 27:
                raise Exception('Bad column count ' + str(line.count(',')) + ' : ' + str(line))

            line = convert_values(line, dtf)

            ## Check to see whether a previous page should be closed.
            if (prev_line['stmtpg'] != line[4] or prev_line['account'] != line[2]) and prev_line['account'] != '':
                ## Close the page: ":62F:D151015EUR1618033889"
                zline = ':62' + prev_line['cbaltyp'] + ':' + prev_line['cbalsgn'] + prev_line['cbaldte'] + prev_line['ccy'] + prev_line['cbal'] + '\n'
                if prev_line['abalsgn'] != '':
                    ## Write available balance line: ":64:C151015EUR4238,05"
                    zline += ':64:' + prev_line['abalsgn'] + prev_line['abaldte'] + prev_line['ccy'] + prev_line['abal'] + '\n'

            ## Check to see whether it's a new message.
            if prev_line['sendbic'] != line[0].upper() or prev_line['recvbic'] != line[1].upper():
                if prev_line['sendbic'] != '':## Close the last message
                    ## Try and get the checksum of the message, and if successful add the CHK field and reset the file.
                    if chk:
                        zline += '-}{5:{CHK:' + chk + '}}\n'
                    else:
                        zline += '-}{5:}\n'
                ## Open the next message
                ## Create Basic Header
                zline += '{1:' + appid + servid + line[0].ljust(12, 'X') + session_no + seqno + '}'

                ## Create Application Header
                if drctn == 'I': ## Inward (From Swift)
                    zline += '{2:I' + msg_type + line[1].ljust(12, 'X') + msg_prty + dlvt_mnty + obs + '}'
                else: ## Outward (To Swift)
                    if mir is True:
                        ## Auto generate mir
                        mir = str(datetime.datetime.today()).replace('-', '')[2:8] + line[0].ljust(12, 'X') + session_no + seqno
                    zline += '{2:O' + msg_type + inp_time + mir + out_date + out_time + msg_prty + '}'
                f113_ = '' if f113 is False else '{113:'+f113+'}' ## Create field 113 if present
                zline += '{3:' + f113_ + '{118:' + mur + '}{4:\n'

            ## Check to see whether a new message should be opened.
            if prev_line['stmtpg'] != line[4] or prev_line['account'] != line[2]:
                if line[26] == '' or line[26].isspace():
                    zline += ':20:MT94050GEN' + str(trn).rjust(6,'0') + '\n'
                    trn += 1
                else:
                    zline += ':20:' + line[26] + '\n'
                zline += ':25:' + line[2] + '\n' + ':28C:' + line[3].rjust(5, '0') + '/' + line[4].rjust(5, '0') + '\n'
                zline += ':60' + line[6] + ':' + line[5] + line[7] + line[24] + line[8] + '\n'
            ## Now add the item line.
            zline += ':61:' + line[9] + line[10] + line[11] + line[12] + line[13] + line[14] + '//' + line[15] + '\n'
            if line[16] and not line[16].isspace():
                zline += line[16] + '\n'
            if msg_type == '940' and line[25] and not line[25].isspace():
                zline += ':86:' + line[25] + '\n'
            zfile.write(zline)
            prev_line['account'] = line[2]
            prev_line['sendbic'] = line[0]
            prev_line['recvbic'] = line[1]
            prev_line['stmtno']  = line[3]
            prev_line['stmtpg']  = line[4]
            prev_line['ccy']     = line[24]
            prev_line['cbalsgn'] = line[17]
            prev_line['cbaltyp'] = line[18]
            prev_line['cbaldte'] = line[19]
            prev_line['cbal']    = line[20]
            prev_line['abalsgn'] = line[21]
            prev_line['abaldte'] = line[22]
            prev_line['abal']    = line[23]
            lst_line = line
        ## Close the last line.
        zline = ':62F:' + lst_line[17] + lst_line[19] + lst_line[24] + lst_line[20] + '\n'
        if lst_line[21] != '':
            ## Write available balance line: ":64:C151015EUR4238,05"
            zline += ':64:' + lst_line[21] + lst_line[22] + lst_line[24] + lst_line[23] + '\n'
        if chk:
            zline += '-}{5:{CHK:' + chk + '}}'
        else:
            zline += '-}{5:}'
        zfile.write(zline)
    print('MT%s created successfully.' % msg_type)
def convert_values(xline, dtf_):
    '''
    Converts supplied values to swift MT equivalents.
    '''
    ## Upper case Types and Signs.
    xline[5], xline[6], xline[11]   = xline[5].upper(), xline[6].upper(), xline[11].upper()
    xline[17], xline[18], xline[21] = xline[17].upper(), xline[18].upper(), xline[21].upper()
    ## All amounts, remove thousands seps, and replace decimal spot with comma
    xline[8]  = xline[8].replace(',', '').replace('.', ',').replace('-', '')  ## Open Bal
    xline[12] = xline[12].replace(',', '').replace('.', ',').replace('-', '') ## Item Amount
    xline[20] = xline[20].replace(',', '').replace('.', ',').replace('-', '') ## Close Bal
    xline[23] = xline[23].replace(',', '').replace('.', ',').replace('-', '') ## Avail Bal
    ## Convert dates to YYMMDD or MMDD
    if dtf_ == 'DDMMYYYY':
        xline[7]  = xline[7][8:10] + xline[7][3:5] + xline[7][:2]    ## Open Bal Date
        xline[9]  = xline[9][8:10] + xline[9][3:5] + xline[9][:2]    ## Item Value Date
        xline[10] = xline[10][3:5] + xline[10][:2]                   ## Item Entry Date
        xline[19] = xline[19][8:10] + xline[19][3:5] + xline[19][:2] ## Close Bal Date
        xline[22] = xline[22][8:10] + xline[22][3:5] + xline[22][:2] ## Avail Bal Date
    elif dtf_ == 'MMDDYYYY':
        xline[7]  = xline[7][8:10] + xline[7][:2] + xline[7][3:5]    ## Open Bal Date
        xline[9]  = xline[9][8:10] + xline[9][:2] + xline[9][3:5]    ## Item Value Date
        xline[10] = xline[10][:2] + xline[10][3:5]                   ## Item Entry Date
        xline[19] = xline[19][8:10] + xline[19][:2] + xline[19][3:5] ## Close Bal Date
        xline[22] = xline[22][8:10] + xline[22][:2] + xline[22][3:5] ## Avail Bal Date
    else: ## YYYYMMDD
        xline[7]  = xline[7][2:4] + xline[7][5:7] + xline[7][8:10]   ## Open Bal Date
        xline[9]  = xline[9][2:4] + xline[9][5:7] + xline[9][8:10]   ## Item Value Date
        xline[10] = xline[10][5:7] + xline[10][8:10]                 ## Item Entry Date
        xline[19] = xline[19][2:4] + xline[19][5:7] + xline[19][8:10]## Close Bal Date
        xline[22] = xline[22][2:4] + xline[22][5:7] + xline[22][8:10]## Avail Bal Date
    return(xline)
